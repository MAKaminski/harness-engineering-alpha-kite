"""Orchestrator: poll loop, dispatch, reconciliation, retry (SPEC.md Section 7, 8, 16)."""
from __future__ import annotations

import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor, Future
from typing import Any, Callable

from .agent_runner import run_agent_attempt
from .config import ServiceConfig, validate_dispatch_config
from .linear_client import (
    LinearClientError,
    fetch_candidate_issues,
    fetch_issue_states_by_ids,
    fetch_issues_by_states,
)
from .models import Issue, OrchestratorState, RetryEntry, RunningEntry
from .workspace_manager import create_for_issue, remove_workspace

logger = logging.getLogger("symphony.orchestrator")

CONTINUATION_RETRY_DELAY_MS = 1000
INITIAL_FAILURE_DELAY_MS = 10000


def _now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _monotonic_ms() -> float:
    return time.monotonic() * 1000


def _normalize_state(s: str) -> str:
    return (s or "").strip().lower()


def _sort_for_dispatch(issues: list[Issue]) -> list[Issue]:
    """Priority ascending, created_at oldest first, identifier tie-breaker."""
    def key(i: Issue) -> tuple:
        priority = i.priority if i.priority is not None else 9999
        created = i.created_at or ""
        return (priority, created, i.identifier)
    return sorted(issues, key=key)


def _is_todo_with_non_terminal_blockers(issue: Issue, terminal_states: list[str]) -> bool:
    if _normalize_state(issue.state) != "todo":
        return False
    term_set = {_normalize_state(s) for s in terminal_states}
    for b in issue.blocked_by:
        bs = _normalize_state(b.state or "") if b.state else ""
        if bs and bs not in term_set:
            return True
    return False


def _available_slots(state: OrchestratorState, config: ServiceConfig) -> int:
    running_count = len(state.running)
    global_limit = config.agent_max_concurrent_agents
    base = max(0, global_limit - running_count)
    # Per-state: count running per state and cap by max_concurrent_agents_by_state
    by_state: dict[str, int] = {}
    for r in state.running.values():
        sn = _normalize_state(r.issue.state)
        by_state[sn] = by_state.get(sn, 0) + 1
    for sn, count in by_state.items():
        cap = config.agent_max_concurrent_by_state(sn)
        if cap is not None and count >= cap:
            return 0
    return base


def _should_dispatch(
    issue: Issue,
    state: OrchestratorState,
    config: ServiceConfig,
) -> bool:
    if not issue.id or not issue.identifier or not issue.title or not issue.state:
        return False
    active_set = {_normalize_state(s) for s in config.tracker_active_states}
    terminal_set = {_normalize_state(s) for s in config.tracker_terminal_states}
    issue_state_n = _normalize_state(issue.state)
    if issue_state_n not in active_set or issue_state_n in terminal_set:
        return False
    if issue.id in state.running or issue.id in state.claimed:
        return False
    if _available_slots(state, config) <= 0:
        return False
    if _is_todo_with_non_terminal_blockers(issue, config.tracker_terminal_states):
        return False
    return True


def _next_retry_attempt(current: int | None, normal_exit: bool) -> int:
    if normal_exit:
        return 1  # continuation
    return (current or 0) + 1


def _retry_delay_ms(attempt: int, config: ServiceConfig) -> int:
    if attempt <= 1:
        return CONTINUATION_RETRY_DELAY_MS
    delay = INITIAL_FAILURE_DELAY_MS * (2 ** (attempt - 1))
    return min(delay, config.agent_max_retry_backoff_ms)


class Orchestrator:
    def __init__(
        self,
        get_workflow_path: Callable[[], str],
        load_workflow: Callable[[str], Any],
        on_state_snapshot: Callable[[dict], None] | None = None,
    ) -> None:
        self._get_workflow_path = get_workflow_path
        self._load_workflow = load_workflow
        self._on_state_snapshot = on_state_snapshot
        self._state: OrchestratorState | None = None
        self._config: ServiceConfig | None = None
        self._prompt_template: str = ""
        self._executor = ThreadPoolExecutor(max_workers=32)
        self._retry_timers: dict[str, threading.Timer] = {}
        self._lock = threading.Lock()
        self._shutdown = False
        self._tick_scheduled = False

    def _load_config(self) -> tuple[ServiceConfig, str] | None:
        """Load workflow; return (config, prompt_template) or None on error."""
        try:
            path = self._get_workflow_path()
            wf = self._load_workflow(path)
            from .config import ServiceConfig
            cfg = ServiceConfig(wf)
            return cfg, wf.prompt_template
        except Exception as e:
            logger.error("workflow load failed workflow_parse_error=%s", e, exc_info=True)
            return None

    def _get_config_and_template(self) -> tuple[ServiceConfig, str] | None:
        loaded = self._load_config()
        if loaded is None and self._config is not None:
            return self._config, self._prompt_template
        if loaded is not None:
            self._config, self._prompt_template = loaded
            return loaded
        return None

    def _reconcile_running(self) -> None:
        """Stall detection + tracker state refresh (Section 8.5)."""
        with self._lock:
            state = self._state
            config = self._config
        if not state or not config:
            return
        stall_ms = config.codex_stall_timeout_ms
        now_ms = _monotonic_ms()
        to_terminate: list[str] = []
        for issue_id, entry in list(state.running.items()):
            ts = entry.last_codex_timestamp or entry.started_at
            try:
                ts_ms = time.mktime(time.strptime(ts.replace("Z", "+0000"), "%Y-%m-%dT%H:%M:%S+0000")) * 1000
            except Exception:
                ts_ms = now_ms - 1000
            elapsed = now_ms - ts_ms
            if stall_ms > 0 and elapsed > stall_ms:
                to_terminate.append(issue_id)
        for issue_id in to_terminate:
            self._terminate_running(issue_id, cleanup_workspace=False, reason="stalled")

        running_ids = list(state.running.keys())
        if not running_ids:
            return
        try:
            refreshed = fetch_issue_states_by_ids(config, running_ids)
        except LinearClientError as e:
            logger.warning("reconciliation state refresh failed: %s", e.message)
            return
        terminal_set = {_normalize_state(s) for s in config.tracker_terminal_states}
        active_set = {_normalize_state(s) for s in config.tracker_active_states}
        by_id = {i.id: i for i in refreshed}
        with self._lock:
            state = self._state
        for issue_id in running_ids:
            issue = by_id.get(issue_id)
            if issue is None:
                continue
            sn = _normalize_state(issue.state)
            if sn in terminal_set:
                self._terminate_running(issue_id, cleanup_workspace=True, reason="terminal")
            elif sn not in active_set:
                self._terminate_running(issue_id, cleanup_workspace=False, reason="inactive")
            else:
                with self._lock:
                    if state and issue_id in state.running:
                        state.running[issue_id].issue = issue

    def _terminate_running(self, issue_id: str, cleanup_workspace: bool, reason: str) -> None:
        with self._lock:
            state = self._state
            config = self._config
            if not state or issue_id not in state.running:
                return
            entry = state.running.pop(issue_id)
            state.claimed.discard(issue_id)
            identifier = entry.identifier
            workspace_path = None
            if config:
                from .workspace_manager import get_workspace_path
                workspace_path = get_workspace_path(config.workspace_root, identifier)
        logger.info("issue_id=%s issue_identifier=%s terminated reason=%s", issue_id, identifier, reason)
        if cleanup_workspace and config and workspace_path:
            try:
                remove_workspace(config, workspace_path, log_fn=logger.warning)
            except Exception as e:
                logger.warning("workspace cleanup failed: %s", e)
        self._add_runtime_seconds(entry)
        self._schedule_retry(issue_id, identifier, _next_retry_attempt(entry.retry_attempt, False), f"terminated: {reason}")

    def _add_runtime_seconds(self, entry: RunningEntry) -> None:
        with self._lock:
            if not self._state:
                return
            try:
                start = time.mktime(time.strptime(entry.started_at.replace("Z", "+0000"), "%Y-%m-%dT%H:%M:%S+0000"))
            except Exception:
                start = time.time()
            secs = max(0, time.time() - start)
            self._state.codex_totals["seconds_running"] = self._state.codex_totals.get("seconds_running", 0) + secs
            self._state.codex_totals["input_tokens"] = self._state.codex_totals.get("input_tokens", 0) + entry.codex_input_tokens
            self._state.codex_totals["output_tokens"] = self._state.codex_totals.get("output_tokens", 0) + entry.codex_output_tokens
            self._state.codex_totals["total_tokens"] = self._state.codex_totals.get("total_tokens", 0) + entry.codex_total_tokens

    def _schedule_retry(self, issue_id: str, identifier: str, attempt: int, error: str | None) -> None:
        delay_ms = _retry_delay_ms(attempt, self._config) if self._config else CONTINUATION_RETRY_DELAY_MS
        due_at_ms = _monotonic_ms() + delay_ms

        def fire() -> None:
            with self._lock:
                state = self._state
                config = self._config
                if not state or issue_id not in state.retry_attempts:
                    return
                state.retry_attempts.pop(issue_id, None)
            self._on_retry_timer(issue_id, identifier, attempt, error)

        t = threading.Timer(delay_ms / 1000.0, fire)
        t.daemon = True
        t.start()
        with self._lock:
            if self._state:
                self._state.retry_attempts[issue_id] = RetryEntry(
                    issue_id=issue_id,
                    identifier=identifier,
                    attempt=attempt,
                    due_at_ms=due_at_ms,
                    timer_handle=t,
                    error=error,
                )
        logger.info("issue_id=%s issue_identifier=%s retry_scheduled attempt=%s due_ms=%s error=%s", issue_id, identifier, attempt, due_at_ms, error)

    def _on_retry_timer(self, issue_id: str, identifier: str, attempt: int, last_error: str | None) -> None:
        config = self._get_config_and_template()
        if not config:
            with self._lock:
                if self._state:
                    self._state.claimed.discard(issue_id)
            return
        cfg, _ = config
        try:
            candidates = fetch_candidate_issues(cfg)
        except LinearClientError as e:
            logger.warning("retry poll failed: %s", e.message)
            self._schedule_retry(issue_id, identifier, attempt + 1, "retry poll failed")
            return
        issue = next((i for i in candidates if i.id == issue_id), None)
        if issue is None:
            with self._lock:
                if self._state:
                    self._state.claimed.discard(issue_id)
            logger.info("issue_id=%s no longer candidate, released", issue_id)
            return
        with self._lock:
            state = self._state
            if _available_slots(state, cfg) == 0:
                self._schedule_retry(issue_id, identifier, attempt + 1, "no available orchestrator slots")
                return
        self._dispatch_issue(issue, attempt)

    def _on_codex_update(self, issue_id: str, event: dict) -> None:
        with self._lock:
            state = self._state
            if not state or issue_id not in state.running:
                return
            entry = state.running[issue_id]
            entry.last_codex_event = event.get("event")
            entry.last_codex_timestamp = event.get("timestamp")
            entry.last_codex_message = str(event.get("last_message", ""))[:500]
            usage = event.get("usage") or {}
            entry.codex_input_tokens = usage.get("input_tokens") or entry.codex_input_tokens
            entry.codex_output_tokens = usage.get("output_tokens") or entry.codex_output_tokens
            entry.codex_total_tokens = usage.get("total_tokens") or entry.codex_total_tokens
            if "turn_count" in event:
                entry.turn_count = event.get("turn_count", entry.turn_count)

    def _dispatch_issue(self, issue: Issue, attempt: int | None) -> None:
        loaded = self._get_config_and_template()
        if not loaded:
            return
        config, prompt_template = loaded
        errors = validate_dispatch_config(config)
        if errors:
            logger.error("dispatch validation failed: %s", errors)
            return
        with self._lock:
            state = self._state
            if not state or issue.id in state.running or issue.id in state.claimed:
                return
            state.claimed.add(issue.id)

        def worker() -> None:
            try:
                workspace = create_for_issue(config, issue.identifier, log_fn=logger.info)
            except Exception as e:
                logger.exception("workspace creation failed issue_id=%s", issue.id)
                with self._lock:
                    if self._state:
                        self._state.claimed.discard(issue.id)
                self._schedule_retry(issue.id, issue.identifier, _next_retry_attempt(attempt, False), str(e))
                return

            def on_event(ev: dict) -> None:
                self._on_codex_update(issue.id, ev)

            success, err = run_agent_attempt(
                config,
                workspace.path,
                issue,
                attempt,
                prompt_template,
                on_event,
            )
            with self._lock:
                state = self._state
                if not state or issue.id not in state.running:
                    return
                entry = state.running.pop(issue.id)
                state.claimed.discard(issue.id)
                if success:
                    state.completed.add(issue.id)
            self._add_runtime_seconds(entry)
            if success:
                self._schedule_retry(issue.id, issue.identifier, 1, None)  # continuation
            else:
                self._schedule_retry(issue.id, issue.identifier, _next_retry_attempt(entry.retry_attempt, False), err or "worker exited")
            self._notify_snapshot()

        def run_and_track() -> None:
            with self._lock:
                state = self._state
                if not state or issue.id not in state.claimed:
                    return
                state.running[issue.id] = RunningEntry(
                    worker_handle=None,
                    identifier=issue.identifier,
                    issue=issue,
                    session_id=None,
                    codex_app_server_pid=None,
                    last_codex_message=None,
                    last_codex_event=None,
                    last_codex_timestamp=None,
                    codex_input_tokens=0,
                    codex_output_tokens=0,
                    codex_total_tokens=0,
                    last_reported_input_tokens=0,
                    last_reported_output_tokens=0,
                    last_reported_total_tokens=0,
                    retry_attempt=attempt or 0,
                    started_at=_now_utc(),
                    turn_count=0,
                )
            try:
                worker()
            except Exception as e:
                logger.exception("worker failed issue_id=%s", issue.id)
                with self._lock:
                    if self._state and issue.id in self._state.running:
                        self._state.running.pop(issue.id)
                    if self._state:
                        self._state.claimed.discard(issue.id)
                self._schedule_retry(issue.id, issue.identifier, _next_retry_attempt(attempt, False), str(e))
            self._notify_snapshot()

        self._executor.submit(run_and_track)

    def _notify_snapshot(self) -> None:
        if self._on_state_snapshot:
            with self._lock:
                state = self._state
                if state:
                    self._on_state_snapshot(self._snapshot(state))

    def _snapshot(self, state: OrchestratorState) -> dict:
        running_list = []
        for issue_id, e in state.running.items():
            running_list.append({
                "issue_id": issue_id,
                "issue_identifier": e.identifier,
                "state": e.issue.state,
                "session_id": e.session_id,
                "turn_count": e.turn_count,
                "started_at": e.started_at,
                "last_codex_event": e.last_codex_event,
                "last_codex_timestamp": e.last_codex_timestamp,
                "codex_input_tokens": e.codex_input_tokens,
                "codex_output_tokens": e.codex_output_tokens,
                "codex_total_tokens": e.codex_total_tokens,
            })
        retrying_list = []
        for issue_id, r in state.retry_attempts.items():
            retrying_list.append({
                "issue_id": issue_id,
                "identifier": r.identifier,
                "attempt": r.attempt,
                "due_at_ms": r.due_at_ms,
                "error": r.error,
            })
        return {
            "running": running_list,
            "retrying": retrying_list,
            "codex_totals": dict(state.codex_totals),
            "rate_limits": state.codex_rate_limits,
        }

    def _tick(self) -> None:
        self._reconcile_running()
        loaded = self._get_config_and_template()
        if not loaded:
            self._schedule_next_tick()
            return
        config, _ = loaded
        errors = validate_dispatch_config(config)
        if errors:
            logger.error("dispatch preflight validation failed: %s", errors)
            self._schedule_next_tick()
            return
        try:
            issues = fetch_candidate_issues(config)
        except LinearClientError as e:
            logger.warning("fetch candidates failed: %s", e.message)
            self._schedule_next_tick()
            return
        for issue in _sort_for_dispatch(issues):
            with self._lock:
                state = self._state
                if not state:
                    break
                if _available_slots(state, config) <= 0:
                    break
            if _should_dispatch(issue, self._state, config):
                self._dispatch_issue(issue, None)
        self._notify_snapshot()
        self._schedule_next_tick()

    def _schedule_next_tick(self) -> None:
        with self._lock:
            if self._shutdown or not self._state:
                return
            interval_ms = self._state.poll_interval_ms
        delay_sec = max(0.001, interval_ms / 1000.0)
        t = threading.Timer(delay_sec, self._tick)
        t.daemon = True
        t.start()

    def start(self) -> None:
        """Load config, validate, startup terminal cleanup, schedule first tick."""
        loaded = self._load_config()
        if not loaded:
            raise RuntimeError("Workflow load failed; cannot start")
        config, prompt_template = loaded
        self._config, self._prompt_template = config, prompt_template
        errors = validate_dispatch_config(config)
        if errors:
            raise RuntimeError(f"Dispatch validation failed: {errors}")
        self._state = OrchestratorState(
            poll_interval_ms=config.poll_interval_ms,
            max_concurrent_agents=config.agent_max_concurrent_agents,
        )
        try:
            terminal_issues = fetch_issues_by_states(config, config.tracker_terminal_states)
            for issue in terminal_issues:
                from .workspace_manager import get_workspace_path
                path = get_workspace_path(config.workspace_root, issue.identifier)
                try:
                    remove_workspace(config, path, log_fn=logger.warning)
                except Exception as e:
                    logger.warning("startup cleanup %s: %s", issue.identifier, e)
        except LinearClientError as e:
            logger.warning("startup terminal cleanup fetch failed: %s", e.message)
        self._tick()

    def stop(self) -> None:
        self._shutdown = True
        for t in list(self._retry_timers.values()):
            t.cancel()
        self._executor.shutdown(wait=True)

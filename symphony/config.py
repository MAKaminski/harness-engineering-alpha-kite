"""Configuration layer: typed getters, defaults, env resolution (SPEC.md Section 6)."""
from __future__ import annotations

import os
import re
from typing import Any

from .models import WorkflowDefinition


def _expand_value(val: Any) -> Any:
    """Expand $VAR and ${VAR} and ~ in string values; only for path/secret-like fields."""
    if not isinstance(val, str):
        return val
    # ${VAR_NAME} or $VAR_NAME (identifier only)
    expanded = re.sub(r"\$\{([^}]+)\}", lambda m: os.environ.get(m.group(1).strip(), ""), val)
    expanded = re.sub(r"\$([A-Za-z_][A-Za-z0-9_]*)", lambda m: os.environ.get(m.group(1), ""), expanded)
    # ~ home expansion
    if "~" in expanded:
        expanded = os.path.expanduser(expanded)
    return expanded


def _get_nested(config: dict[str, Any], key_path: str, default: Any = None) -> Any:
    keys = key_path.split(".")
    cur: Any = config
    for k in keys:
        if not isinstance(cur, dict) or k not in cur:
            return default
        cur = cur[k]
    return cur


def _list_or_comma_string(val: Any) -> list[str]:
    if val is None:
        return []
    if isinstance(val, list):
        return [str(x).strip() for x in val if x is not None]
    if isinstance(val, str):
        return [s.strip() for s in val.split(",") if s.strip()]
    return []


def _int_coerce(val: Any, default: int) -> int:
    if val is None:
        return default
    try:
        return int(val)
    except (TypeError, ValueError):
        return default


# --- Defaults (Section 6.4) ---
LINEAR_ENDPOINT = "https://api.linear.app/graphql"
DEFAULT_ACTIVE_STATES = ["Todo", "In Progress"]
DEFAULT_TERMINAL_STATES = ["Closed", "Cancelled", "Canceled", "Duplicate", "Done"]
DEFAULT_POLL_INTERVAL_MS = 30000
DEFAULT_WORKSPACE_ROOT = os.path.join(os.path.abspath(os.environ.get("TEMP", os.environ.get("TMPDIR", "/tmp"))), "symphony_workspaces")
DEFAULT_HOOKS_TIMEOUT_MS = 60000
DEFAULT_MAX_CONCURRENT_AGENTS = 10
DEFAULT_MAX_TURNS = 20
DEFAULT_MAX_RETRY_BACKOFF_MS = 300000
DEFAULT_CODEX_COMMAND = "codex app-server"
DEFAULT_TURN_TIMEOUT_MS = 3600000
DEFAULT_READ_TIMEOUT_MS = 5000
DEFAULT_STALL_TIMEOUT_MS = 300000


class ServiceConfig:
    """Typed view over workflow config + env resolution."""

    def __init__(self, definition: WorkflowDefinition) -> None:
        self._config = definition.config or {}

    def _tracker(self) -> dict[str, Any]:
        return self._config.get("tracker") or {}

    def _polling(self) -> dict[str, Any]:
        return self._config.get("polling") or {}

    def _workspace(self) -> dict[str, Any]:
        return self._config.get("workspace") or {}

    def _hooks(self) -> dict[str, Any]:
        return self._config.get("hooks") or {}

    def _agent(self) -> dict[str, Any]:
        return self._config.get("agent") or {}

    def _codex(self) -> dict[str, Any]:
        return self._config.get("codex") or {}

    @property
    def tracker_kind(self) -> str:
        return (self._tracker().get("kind") or "").strip()

    @property
    def tracker_endpoint(self) -> str:
        val = self._tracker().get("endpoint") or (LINEAR_ENDPOINT if self.tracker_kind == "linear" else "")
        return (val or LINEAR_ENDPOINT).strip()

    @property
    def tracker_api_key(self) -> str:
        raw = self._tracker().get("api_key") or ""
        return _expand_value(raw) if isinstance(raw, str) else ""

    @property
    def tracker_project_slug(self) -> str:
        return (self._tracker().get("project_slug") or "").strip()

    @property
    def tracker_active_states(self) -> list[str]:
        val = self._tracker().get("active_states")
        if val is None:
            return list(DEFAULT_ACTIVE_STATES)
        return _list_or_comma_string(val)

    @property
    def tracker_terminal_states(self) -> list[str]:
        val = self._tracker().get("terminal_states")
        if val is None:
            return list(DEFAULT_TERMINAL_STATES)
        return _list_or_comma_string(val)

    @property
    def poll_interval_ms(self) -> int:
        val = _get_nested(self._config, "polling.interval_ms")
        return _int_coerce(val, DEFAULT_POLL_INTERVAL_MS)

    @property
    def workspace_root(self) -> str:
        val = self._workspace().get("root")
        if val is None or val == "":
            return DEFAULT_WORKSPACE_ROOT
        expanded = _expand_value(val) if isinstance(val, str) else val
        if isinstance(expanded, str) and ("/" in expanded or "\\" in expanded or expanded.startswith("~")):
            return os.path.abspath(os.path.expanduser(expanded))
        return str(expanded)

    @property
    def hooks_after_create(self) -> str | None:
        v = self._hooks().get("after_create")
        return v.strip() if isinstance(v, str) and v.strip() else None

    @property
    def hooks_before_run(self) -> str | None:
        v = self._hooks().get("before_run")
        return v.strip() if isinstance(v, str) and v.strip() else None

    @property
    def hooks_after_run(self) -> str | None:
        v = self._hooks().get("after_run")
        return v.strip() if isinstance(v, str) and v.strip() else None

    @property
    def hooks_before_remove(self) -> str | None:
        v = self._hooks().get("before_remove")
        return v.strip() if isinstance(v, str) and v.strip() else None

    @property
    def hooks_timeout_ms(self) -> int:
        val = self._hooks().get("timeout_ms")
        n = _int_coerce(val, DEFAULT_HOOKS_TIMEOUT_MS)
        return n if n > 0 else DEFAULT_HOOKS_TIMEOUT_MS

    @property
    def agent_max_concurrent_agents(self) -> int:
        val = _get_nested(self._config, "agent.max_concurrent_agents")
        return max(1, _int_coerce(val, DEFAULT_MAX_CONCURRENT_AGENTS))

    @property
    def agent_max_turns(self) -> int:
        val = _get_nested(self._config, "agent.max_turns")
        return max(1, _int_coerce(val, DEFAULT_MAX_TURNS))

    @property
    def agent_max_retry_backoff_ms(self) -> int:
        val = _get_nested(self._config, "agent.max_retry_backoff_ms")
        return _int_coerce(val, DEFAULT_MAX_RETRY_BACKOFF_MS)

    def agent_max_concurrent_by_state(self, state_normalized: str) -> int | None:
        m = self._agent().get("max_concurrent_agents_by_state")
        if not isinstance(m, dict):
            return None
        v = m.get(state_normalized)
        if v is None:
            return None
        try:
            n = int(v)
            return n if n > 0 else None
        except (TypeError, ValueError):
            return None

    @property
    def codex_command(self) -> str:
        val = self._codex().get("command") or DEFAULT_CODEX_COMMAND
        return (val or DEFAULT_CODEX_COMMAND).strip()

    @property
    def codex_approval_policy(self) -> str:
        return (self._codex().get("approval_policy") or "auto").strip()

    @property
    def codex_thread_sandbox(self) -> str:
        return (self._codex().get("thread_sandbox") or "relaxed").strip()

    @property
    def codex_turn_sandbox_policy(self) -> str:
        return (self._codex().get("turn_sandbox_policy") or "relaxed").strip()

    @property
    def codex_turn_timeout_ms(self) -> int:
        val = self._codex().get("turn_timeout_ms")
        return _int_coerce(val, DEFAULT_TURN_TIMEOUT_MS)

    @property
    def codex_read_timeout_ms(self) -> int:
        val = self._codex().get("read_timeout_ms")
        return _int_coerce(val, DEFAULT_READ_TIMEOUT_MS)

    @property
    def codex_stall_timeout_ms(self) -> int:
        val = self._codex().get("stall_timeout_ms")
        return _int_coerce(val, DEFAULT_STALL_TIMEOUT_MS)


def validate_dispatch_config(config: ServiceConfig) -> list[str]:
    """Dispatch preflight validation (Section 6.3). Returns list of error messages."""
    errors: list[str] = []
    if not config.tracker_kind:
        errors.append("tracker.kind is required")
    elif config.tracker_kind != "linear":
        errors.append(f"unsupported tracker.kind: {config.tracker_kind}")
    if not config.tracker_api_key:
        errors.append("tracker.api_key is required (set LINEAR_API_KEY or configure in workflow)")
    if config.tracker_kind == "linear" and not config.tracker_project_slug:
        errors.append("tracker.project_slug is required when tracker.kind is linear")
    if not config.codex_command:
        errors.append("codex.command is required")
    return errors

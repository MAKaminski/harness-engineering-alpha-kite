"""Domain models for Symphony (see SPEC.md Section 4)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, TypedDict


# --- Blocker ref (Section 4.1.1) ---
@dataclass(frozen=True)
class BlockerRef:
    id: str | None
    identifier: str | None
    state: str | None


# --- Issue (Section 4.1.1) ---
@dataclass
class Issue:
    id: str
    identifier: str
    title: str
    description: str | None
    priority: int | None
    state: str
    branch_name: str | None
    url: str | None
    labels: list[str]
    blocked_by: list[BlockerRef]
    created_at: str | None
    updated_at: str | None

    def state_normalized(self) -> str:
        return self.state.strip().lower()


# --- Workflow definition (Section 4.1.2) ---
@dataclass
class WorkflowDefinition:
    config: dict[str, Any]
    prompt_template: str


# --- Workspace (Section 4.1.4) ---
@dataclass
class Workspace:
    path: str
    workspace_key: str
    created_now: bool


# --- Run attempt status (Section 7.2) ---
RUN_ATTEMPT_STATUSES = (
    "PreparingWorkspace",
    "BuildingPrompt",
    "LaunchingAgentProcess",
    "InitializingSession",
    "StreamingTurn",
    "Finishing",
    "Succeeded",
    "Failed",
    "TimedOut",
    "Stalled",
    "CanceledByReconciliation",
)


# --- Live session (Section 4.1.6) ---
@dataclass
class LiveSession:
    session_id: str
    thread_id: str
    turn_id: str
    codex_app_server_pid: str | None
    last_codex_event: str | None
    last_codex_timestamp: str | None
    last_codex_message: str | None
    codex_input_tokens: int
    codex_output_tokens: int
    codex_total_tokens: int
    last_reported_input_tokens: int
    last_reported_output_tokens: int
    last_reported_total_tokens: int
    turn_count: int


# --- Retry entry (Section 4.1.7) ---
@dataclass
class RetryEntry:
    issue_id: str
    identifier: str
    attempt: int
    due_at_ms: float
    timer_handle: Any  # runtime-specific
    error: str | None


# --- Running entry (orchestrator state) ---
@dataclass
class RunningEntry:
    worker_handle: Any  # Future or Thread
    identifier: str
    issue: Issue
    session_id: str | None
    codex_app_server_pid: str | None
    last_codex_message: str | None
    last_codex_event: str | None
    last_codex_timestamp: str | None
    codex_input_tokens: int
    codex_output_tokens: int
    codex_total_tokens: int
    last_reported_input_tokens: int
    last_reported_output_tokens: int
    last_reported_total_tokens: int
    retry_attempt: int
    started_at: str
    turn_count: int = 0


# --- Codex totals (Section 4.1.8) ---
class CodexTotals(TypedDict, total=False):
    input_tokens: int
    output_tokens: int
    total_tokens: int
    seconds_running: float


# --- Orchestrator runtime state (Section 4.1.8) ---
@dataclass
class OrchestratorState:
    poll_interval_ms: int
    max_concurrent_agents: int
    running: dict[str, RunningEntry] = field(default_factory=dict)
    claimed: set[str] = field(default_factory=set)
    retry_attempts: dict[str, RetryEntry] = field(default_factory=dict)
    completed: set[str] = field(default_factory=set)
    codex_totals: CodexTotals = field(default_factory=lambda: {
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
        "seconds_running": 0.0,
    })
    codex_rate_limits: dict[str, Any] | None = None

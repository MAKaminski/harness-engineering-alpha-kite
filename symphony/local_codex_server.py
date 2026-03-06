"""Minimal local Codex-compatible app-server over stdio.

This is a very small implementation of the SPEC Section 10 protocol:
- Reads line-delimited JSON requests on stdin
- Writes line-delimited JSON responses / notifications on stdout

It does NOT talk to a real LLM yet – it just fabricates a trivial
response and token usage so that Symphony's token accounting and
dashboard work end-to-end without relying on an external `codex app-server`.
"""

from __future__ import annotations

import json
import os
import re
import sys
import uuid
from typing import Any, Dict

try:
    # OpenAI Python client (reads OPENAI_API_KEY from env by default)
    from openai import OpenAI

    _openai_client = OpenAI()
except Exception:
    _openai_client = None

try:
    # Optional Linear client helper (available when running as a package module)
    from symphony.linear_client import LINEAR_GRAPHQL_ENDPOINT, transition_issue_to_state
except Exception:
    LINEAR_GRAPHQL_ENDPOINT = "https://api.linear.app/graphql"

    def transition_issue_to_state(endpoint: str, api_key: str, issue_id: str, state_name: str) -> None:  # type: ignore[no-redef]
        raise RuntimeError("transition_issue_to_state is not available")


def _write(msg: Dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(msg) + "\n")
    sys.stdout.flush()


def _estimate_tokens(text: str) -> int:
    # Very rough heuristic: ~4 chars per token
    return max(1, len(text) // 4) if text else 1


def _extract_issue_id_from_prompt(text: str) -> str | None:
    """Parse Linear issue ID from the rendered prompt body.

    Expected pattern (from WORKFLOW.md prompt template):
    **Issue ID (Linear):** <ISSUE_ID>
    """
    if not text:
        return None
    m = re.search(r"Issue ID \(Linear\):\s*([A-Za-z0-9_-]+)", text)
    if not m:
        return None
    return m.group(1)


def _extract_issue_identifier_from_prompt(text: str) -> str | None:
    """Best-effort parse of issue identifier from the prompt first line."""
    if not text:
        return None
    # Matches lines like: "**Issue:** AK-123 – Some title"
    for line in text.splitlines():
        if "Issue" in line:
            m = re.search(r"\b([A-Z]+-\d+)\b", line)
            if m:
                return m.group(1)
    return None


def main() -> None:
    thread_id = f"thread-{uuid.uuid4()}"
    turn_counter = 0

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue

        method = obj.get("method")
        msg_id = obj.get("id")

        # 1. initialize request
        if method == "initialize" and msg_id is not None:
            _write(
                {
                    "id": msg_id,
                    "result": {
                        "capabilities": {},
                    },
                }
            )
            continue

        # 2. initialized notification from client – ignore
        if method == "initialized":
            continue

        # 3. thread/start – return a synthetic thread id
        if method == "thread/start" and msg_id is not None:
            _write(
                {
                    "id": msg_id,
                    "result": {
                        "thread": {"id": thread_id},
                    },
                }
            )
            continue

        # 4. turn/start – perform a minimal workspace action, optionally update Linear, then emit turn/completed
        if method == "turn/start" and msg_id is not None:
            turn_counter += 1
            turn_id = f"turn-{turn_counter}"

            params = obj.get("params") or {}
            input_items = params.get("input") or []
            text_input = ""
            if isinstance(input_items, list) and input_items:
                first = input_items[0] or {}
                if isinstance(first, dict):
                    text_input = str(first.get("text") or "")

            # Workspace: resolve cwd and write a small progress marker file.
            cwd = params.get("cwd") or os.getcwd()
            issue_id = _extract_issue_id_from_prompt(text_input)
            issue_identifier = _extract_issue_identifier_from_prompt(text_input)
            try:
                progress_path = os.path.join(cwd, "SYMPHONY_PROGRESS.txt")
                with open(progress_path, "a", encoding="utf-8") as f:
                    label = issue_identifier or issue_id or "unknown-issue"
                    f.write(f"{label} turn={turn_id}\n")
            except Exception:
                # Workspace writes are best-effort; never break the protocol on failure.
                pass

            # Optional: attempt to transition the Linear issue to a terminal state (e.g. Done).
            task_done = False
            linear_api_key = os.environ.get("LINEAR_API_KEY", "").strip()
            linear_endpoint = os.environ.get("LINEAR_GRAPHQL_ENDPOINT", LINEAR_GRAPHQL_ENDPOINT).strip() or LINEAR_GRAPHQL_ENDPOINT
            terminal_state_name = os.environ.get("LINEAR_TERMINAL_STATE_NAME", "Done")
            if issue_id and linear_api_key:
                try:
                    transition_issue_to_state(linear_endpoint, linear_api_key, issue_id, terminal_state_name)
                    task_done = True
                except Exception:
                    # Linear failures should not crash the app-server; fallback to normal behavior.
                    task_done = False

            # Default to heuristic usage; replace with real LLM usage if available
            input_tokens = _estimate_tokens(text_input)
            output_tokens = max(1, input_tokens // 2)
            total_tokens = input_tokens + output_tokens

            # If OpenAI client is available, use it to get real token usage.
            # Any failure here falls back to the heuristic above so the protocol
            # stays healthy even if the LLM is unavailable.
            if _openai_client is not None and text_input:
                try:
                    model = os.environ.get("OPENAI_MODEL", "gpt-4.1-mini")
                    resp = _openai_client.chat.completions.create(
                        model=model,
                        messages=[
                            {
                                "role": "system",
                                "content": (
                                    "You are an autonomous coding agent running inside a "
                                    "Symphony workspace. Think step-by-step and focus on "
                                    "practical actions that modify the repo to resolve the issue."
                                ),
                            },
                            {
                                "role": "user",
                                "content": text_input,
                            },
                        ],
                    )

                    usage = getattr(resp, "usage", None)
                    if usage is not None:
                        # OpenAI usage fields: prompt_tokens, completion_tokens, total_tokens
                        input_tokens = getattr(usage, "prompt_tokens", input_tokens) or input_tokens
                        output_tokens = getattr(usage, "completion_tokens", output_tokens) or output_tokens
                        total_tokens = getattr(usage, "total_tokens", input_tokens + output_tokens) or (
                            input_tokens + output_tokens
                        )
                except Exception:
                    # Swallow LLM errors and fall back to heuristic usage.
                    pass

            # turn/start result
            _write({"id": msg_id, "result": {"turn": {"id": turn_id}}})

            # turn/completed notification with usage under params.turn.usage
            _write(
                {
                    "method": "turn/completed",
                    "params": {
                        "threadId": thread_id,
                        "turn": {
                            "id": turn_id,
                            "usage": {
                                "inputTokens": input_tokens,
                                "outputTokens": output_tokens,
                                "totalTokens": total_tokens,
                            },
                            # Optional extension consumed by the agent_runner: when true, the
                            # runner exits the turn loop after this turn and marks the attempt
                            # as a success instead of continuing up to max_turns.
                            "taskDone": task_done,
                        },
                    },
                }
            )
            continue

        # Anything else – ignore for now


if __name__ == "__main__":
    main()


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
import sys
import uuid
from typing import Any, Dict


def _write(msg: Dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(msg) + "\n")
    sys.stdout.flush()


def _estimate_tokens(text: str) -> int:
    # Very rough heuristic: ~4 chars per token
    return max(1, len(text) // 4) if text else 1


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

        # 4. turn/start – echo a dummy response and emit turn/completed
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

            input_tokens = _estimate_tokens(text_input)
            output_tokens = max(1, input_tokens // 2)
            total_tokens = input_tokens + output_tokens

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
                        },
                    },
                }
            )
            continue

        # Anything else – ignore for now


if __name__ == "__main__":
    main()


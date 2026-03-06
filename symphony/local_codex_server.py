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
import sys
import uuid
from typing import Any, Dict

try:
    # OpenAI Python client (reads OPENAI_API_KEY from env by default)
    from openai import OpenAI

    _openai_client = OpenAI()
except Exception:
    _openai_client = None


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
                        },
                    },
                }
            )
            continue

        # Anything else – ignore for now


if __name__ == "__main__":
    main()


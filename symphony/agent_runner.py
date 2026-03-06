"""Agent runner: Codex app-server subprocess client over stdio (SPEC.md Section 10)."""
from __future__ import annotations

import json
import logging
import os
import queue
import subprocess
import sys
import threading
import time
from typing import Any, Callable

from .config import ServiceConfig
from .models import Issue
from .prompt import render_prompt
from .workspace_manager import run_after_run, run_before_run

logger = logging.getLogger("symphony.agent_runner")

# Max line size for protocol (spec recommends 10 MB)
MAX_LINE_BYTES = 10 * 1024 * 1024

# Use PTY for stdout when available so the child line-buffers (avoids block buffering over pipe)
_use_pty = sys.platform != "win32"
try:
    import pty
except ImportError:
    _use_pty = False


def _now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _emit(
    on_event: Callable[[dict], None],
    event: str,
    payload: dict[str, Any] | None = None,
) -> None:
    data: dict[str, Any] = {"event": event, "timestamp": _now_utc()}
    if payload:
        data.update(payload)
    on_event(data)


def _read_json_from_line(line: str) -> dict | None:
    line = line.strip()
    if not line:
        return None
    try:
        return json.loads(line)
    except json.JSONDecodeError:
        return None


def _extract_thread_id(result: dict) -> str | None:
    """thread/start result -> result.thread.id"""
    r = result.get("result")
    if not isinstance(r, dict):
        return None
    t = r.get("thread")
    if isinstance(t, dict) and t.get("id"):
        return str(t["id"])
    return r.get("threadId")


def _extract_turn_id(result: dict) -> str | None:
    """turn/start result -> result.turn.id"""
    r = result.get("result")
    if not isinstance(r, dict):
        return None
    t = r.get("turn")
    if isinstance(t, dict) and t.get("id"):
        return str(t["id"])
    return r.get("turnId")


def _extract_usage(msg: dict) -> dict[str, int]:
    """Extract input/output/total token counts from various payload shapes (top-level or params)."""
    usage: dict[str, int] = {}

    def merge(u: dict) -> None:
        if not isinstance(u, dict):
            return
        for k, v in u.items():
            if isinstance(v, (int, float)):
                usage[k] = int(v)
        # Normalize camelCase from Codex
        for key in ("inputTokens", "outputTokens", "totalTokens"):
            if key in u and isinstance(u[key], (int, float)):
                n = int(u[key])
                if "input" in key.lower():
                    usage["input_tokens"] = n
                elif "output" in key.lower():
                    usage["output_tokens"] = n
                else:
                    usage["total_tokens"] = n

    for key in ("input_tokens", "output_tokens", "total_tokens", "inputTokens", "outputTokens", "totalTokens"):
        if key in msg and isinstance(msg[key], (int, float)):
            n = int(msg[key])
            if "Tokens" in key:
                usage["input_tokens" if "input" in key.lower() else "output_tokens" if "output" in key.lower() else "total_tokens"] = n
            else:
                usage[key] = n
    merge(msg.get("usage"))
    params = msg.get("params") or {}
    # Common shapes:
    # - top-level: usage
    # - params: { usage }
    # - params: { turn: { usage } }
    merge(params.get("usage"))
    turn = params.get("turn") or {}
    if isinstance(turn, dict):
        merge(turn.get("usage"))
    return usage


def run_agent_attempt(
    config: ServiceConfig,
    workspace_path: str,
    issue: Issue,
    attempt: int | None,
    prompt_template: str,
    on_event: Callable[[dict], None],
) -> tuple[bool, str | None]:
    """
    Run one agent attempt: create session, run turns up to max_turns, then exit.
    Returns (success, error_message). On failure, error_message is set.
    High-trust: auto-approve; user input required -> fail immediately.
    """
    # Validate cwd == workspace_path (Section 9.5)
    workspace_path_abs = os.path.abspath(workspace_path)
    root_abs = os.path.abspath(config.workspace_root)
    if not workspace_path_abs.startswith(root_abs + os.sep) and workspace_path_abs != root_abs:
        _emit(on_event, "startup_failed", {"error": "invalid_workspace_cwd"})
        return False, "invalid_workspace_cwd"

    run_before_run(config, workspace_path_abs)
    read_timeout_sec = max(1, config.codex_read_timeout_ms // 1000)
    turn_timeout_sec = max(1, config.codex_turn_timeout_ms // 1000)
    max_turns = config.agent_max_turns
    approval_policy = config.codex_approval_policy
    sandbox = config.codex_thread_sandbox
    sandbox_policy = config.codex_turn_sandbox_policy

    pty_master: int | None = None
    stdout_file: Any = None
    try:
        if _use_pty:
            pty_master, slave = pty.openpty()
            try:
                proc = subprocess.Popen(
                    ["bash", "-lc", config.codex_command],
                    cwd=workspace_path_abs,
                    stdin=subprocess.PIPE,
                    stdout=slave,
                    stderr=subprocess.PIPE,
                    text=False,
                )
            finally:
                os.close(slave)
        else:
            proc = subprocess.Popen(
                ["bash", "-lc", config.codex_command],
                cwd=workspace_path_abs,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
            )
            stdout_file = proc.stdout
    except FileNotFoundError:
        if pty_master is not None:
            try:
                os.close(pty_master)
            except OSError:
                pass
        run_after_run(config, workspace_path_abs)
        _emit(on_event, "startup_failed", {"error": "codex_not_found"})
        return False, "codex_not_found"
    except Exception as e:
        if pty_master is not None:
            try:
                os.close(pty_master)
            except OSError:
                pass
        run_after_run(config, workspace_path_abs)
        _emit(on_event, "startup_failed", {"error": str(e)})
        return False, "response_error"

    pid_str = str(proc.pid) if proc.pid else None
    stdin = proc.stdin
    stderr = proc.stderr
    if not stdin:
        proc.kill()
        if pty_master is not None:
            try:
                os.close(pty_master)
            except OSError:
                pass
        run_after_run(config, workspace_path_abs)
        return False, "response_error"

    # Incoming message queue (reader thread puts parsed lines here)
    msg_queue: queue.Queue[dict | None] = queue.Queue()

    def read_stdout_chunk() -> str:
        if pty_master is not None:
            try:
                data = os.read(pty_master, 4096)
                return data.decode("utf-8", errors="replace")
            except OSError:
                return ""
        if stdout_file:
            return stdout_file.read(4096)
        return ""

    def reader() -> None:
        line_buf = ""
        try:
            while proc.poll() is None:
                chunk = read_stdout_chunk()
                if not chunk:
                    time.sleep(0.05)
                    continue
                line_buf += chunk
                while "\n" in line_buf:
                    line, line_buf = line_buf.split("\n", 1)
                    if len(line) > MAX_LINE_BYTES:
                        continue
                    obj = _read_json_from_line(line)
                    if obj is not None:
                        msg_queue.put(obj)
            # Drain remaining data (e.g. after process exits)
            while True:
                chunk = read_stdout_chunk()
                if not chunk:
                    break
                line_buf += chunk
                while "\n" in line_buf:
                    line, line_buf = line_buf.split("\n", 1)
                    if len(line) <= MAX_LINE_BYTES:
                        obj = _read_json_from_line(line)
                        if obj is not None:
                            msg_queue.put(obj)
        except Exception:
            pass
        finally:
            if pty_master is not None:
                try:
                    os.close(pty_master)
                except OSError:
                    pass
        msg_queue.put(None)  # EOF sentinel

    read_thread = threading.Thread(target=reader, daemon=True)
    read_thread.start()

    def read_response(timeout_sec: float) -> dict | None:
        deadline = time.monotonic() + timeout_sec
        while time.monotonic() < deadline:
            try:
                obj = msg_queue.get(timeout=min(1.0, max(0.1, deadline - time.monotonic())))
            except queue.Empty:
                continue
            if obj is None:
                return None
            if "result" in obj or "error" in obj:
                return obj
            # Not a request/response; could forward to on_event for streaming notifications
        return None

    def send(msg: dict) -> None:
        try:
            payload = (json.dumps(msg) + "\n").encode("utf-8") if pty_master is not None else (json.dumps(msg) + "\n")
            stdin.write(payload)
            stdin.flush()
        except (BrokenPipeError, OSError):
            pass

    # 1. initialize
    logger.info("codex handshake: waiting for initialize response (timeout_sec=%s)", read_timeout_sec)
    send({"id": 1, "method": "initialize", "params": {"clientInfo": {"name": "symphony", "version": "1.0"}, "capabilities": {}}})
    init_resp = read_response(read_timeout_sec)
    if init_resp is None or "error" in init_resp:
        logger.warning("codex handshake: initialize failed (timeout=%s)", init_resp is None)
        proc.terminate()
        run_after_run(config, workspace_path_abs)
        _emit(on_event, "startup_failed", {"error": "response_timeout" if init_resp is None else init_resp.get("error")})
        return False, "response_timeout" if init_resp is None else "response_error"
    logger.info("codex handshake: initialize OK")
    # 2. initialized notification
    send({"method": "initialized", "params": {}})
    # 3. thread/start
    logger.info("codex handshake: waiting for thread/start response (timeout_sec=%s)", read_timeout_sec)
    send({
        "id": 2,
        "method": "thread/start",
        "params": {
            "approvalPolicy": approval_policy,
            "sandbox": sandbox,
            "cwd": workspace_path_abs,
        },
    })
    thread_resp = read_response(read_timeout_sec)
    if thread_resp is None or "error" in thread_resp:
        logger.warning("codex handshake: thread/start failed (timeout=%s)", thread_resp is None)
        proc.terminate()
        run_after_run(config, workspace_path_abs)
        return False, "response_timeout" if thread_resp is None else "response_error"
    logger.info("codex handshake: thread/start OK")
    thread_id = _extract_thread_id(thread_resp)
    if not thread_id:
        proc.terminate()
        run_after_run(config, workspace_path_abs)
        return False, "response_error"
    turn_id = None
    session_id = f"{thread_id}-"
    _emit(on_event, "session_started", {"thread_id": thread_id, "codex_app_server_pid": pid_str})

    turn_number = 1
    current_prompt: str
    try:
        current_prompt = render_prompt(prompt_template, issue, attempt)
    except Exception as e:
        proc.terminate()
        run_after_run(config, workspace_path_abs)
        return False, "template_render_error"
    title = f"{issue.identifier}: {issue.title}"[:200]

    while turn_number <= max_turns:
        # First turn can be slow (model load, long prompt); use at least 5 min for turn/start response
        turn_read_timeout = max(read_timeout_sec, 300) if turn_number == 1 else read_timeout_sec
        logger.info("codex turn %s: waiting for turn/start response (timeout_sec=%s)", turn_number, turn_read_timeout)
        send({
            "id": 3 + turn_number,
            "method": "turn/start",
            "params": {
                "threadId": thread_id,
                "input": [{"type": "text", "text": current_prompt}],
                "cwd": workspace_path_abs,
                "title": title,
                "approvalPolicy": approval_policy,
                "sandboxPolicy": {"type": sandbox_policy},
            },
        })
        turn_resp = read_response(turn_read_timeout)
        if turn_resp is None or "error" in turn_resp:
            if turn_resp and "error" in turn_resp:
                logger.warning("codex turn %s: turn/start error: %s", turn_number, turn_resp.get("error"))
            else:
                logger.warning("codex turn %s: turn/start failed (timeout=%s)", turn_number, turn_resp is None)
            proc.terminate()
            run_after_run(config, workspace_path_abs)
            return False, "response_timeout" if turn_resp is None else "turn_failed"
        logger.info("codex turn %s: turn/start OK", turn_number)
        turn_id = _extract_turn_id(turn_resp)
        if turn_id:
            session_id = f"{thread_id}-{turn_id}"
            _emit(on_event, "session_started", {"session_id": session_id, "turn_id": turn_id, "turn_count": turn_number})

        # Stream until turn/completed, turn/failed, turn/cancelled or timeout (consume from queue)
        turn_done = False
        turn_success = False
        deadline = time.monotonic() + turn_timeout_sec
        while time.monotonic() < deadline and not turn_done:
            if proc.poll() is not None:
                run_after_run(config, workspace_path_abs)
                return False, "port_exit"
            try:
                obj = msg_queue.get(timeout=min(1.0, max(0.1, deadline - time.monotonic())))
            except queue.Empty:
                continue
            if obj is None:
                break
            method = obj.get("method") or obj.get("event")
            if method == "turn/completed":
                turn_done = True
                turn_success = True
                usage = _extract_usage(obj)
                logger.info(
                    "codex turn %s: turn_completed usage_from_codex=%s (keys in message: %s)",
                    turn_number,
                    usage,
                    list(obj.keys()),
                )
                if not usage and isinstance(obj.get("params"), dict):
                    logger.debug("codex turn/completed params=%s", list(obj["params"].keys()))
                _emit(on_event, "turn_completed", {"usage": usage, "turn_count": turn_number})
            elif method in ("turn/failed", "turn/cancelled"):
                turn_done = True
                _emit(on_event, "turn_failed" if method == "turn/failed" else "turn_cancelled", {"payload": obj})
            elif "params" in obj:
                params = obj["params"] or {}
                if _is_user_input_required(obj):
                    run_after_run(config, workspace_path_abs)
                    proc.terminate()
                    _emit(on_event, "turn_input_required", {})
                    return False, "turn_input_required"
                # Approval: auto-approve
                req_id = obj.get("id")
                if req_id is not None and _is_approval_request(obj):
                    send({"id": req_id, "result": {"approved": True}})
                    _emit(on_event, "approval_auto_approved", {"id": req_id})
                # Unsupported tool
                if _is_tool_call(obj):
                    tool_name = (params.get("name") or params.get("toolName") or "")
                    if tool_name and tool_name != "linear_graphql":
                        send({"id": obj.get("id"), "result": {"success": False, "error": "unsupported_tool_call"}})
                        _emit(on_event, "unsupported_tool_call", {"name": tool_name})
            usage = _extract_usage(obj)
            if usage:
                _emit(on_event, "notification", {"usage": usage, "turn_count": turn_number})

        if not turn_done:
            proc.terminate()
            run_after_run(config, workspace_path_abs)
            return False, "turn_timeout"
        if not turn_success:
            run_after_run(config, workspace_path_abs)
            return False, "turn_failed"
        turn_number += 1
        if turn_number <= max_turns:
            current_prompt = "Continue with the next step for this issue."  # continuation guidance

    proc.terminate()
    run_after_run(config, workspace_path_abs)
    return True, None


def _is_user_input_required(obj: dict) -> bool:
    method = (obj.get("method") or obj.get("event") or "").lower()
    if "userinput" in method or "user_input" in method or method == "item/tool/requestUserInput":
        return True
    params = obj.get("params") or {}
    return params.get("userInputRequired") is True or params.get("inputRequired") is True


def _is_approval_request(obj: dict) -> bool:
    method = (obj.get("method") or obj.get("event") or "").lower()
    return "approval" in method or "approve" in method


def _is_tool_call(obj: dict) -> bool:
    method = (obj.get("method") or obj.get("event") or "").lower()
    return "tool" in method and "call" in method

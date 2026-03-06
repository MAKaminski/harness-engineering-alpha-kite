"""Workspace manager: per-issue paths, hooks, lifecycle (SPEC.md Section 9)."""
from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Callable

from .config import ServiceConfig
from .models import Workspace


# Workspace key: only [A-Za-z0-9._-] (Section 4.2)
SANITIZE_PATTERN = re.compile(r"[^A-Za-z0-9._-]+")


def sanitize_workspace_key(identifier: str) -> str:
    """Replace any character not in [A-Za-z0-9._-] with _."""
    return SANITIZE_PATTERN.sub("_", identifier)


def get_workspace_path(root: str, identifier: str) -> str:
    """Absolute path for issue workspace; must be under root."""
    key = sanitize_workspace_key(identifier)
    return os.path.join(root, key)


def _run_hook(
    script: str,
    cwd: str,
    timeout_ms: int,
    label: str,
) -> None:
    """Run shell script in cwd with timeout. Raises on failure or timeout."""
    timeout_sec = max(1, timeout_ms // 1000)
    proc = subprocess.run(
        ["bash", "-lc", script],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=timeout_sec,
    )
    if proc.returncode != 0:
        stderr = (proc.stderr or "")[:500]
        raise RuntimeError(f"{label} hook failed exit_code={proc.returncode} stderr={stderr!r}")


def _run_hook_best_effort(
    script: str | None,
    cwd: str,
    timeout_ms: int,
    label: str,
    log_fn: Callable[[str], None],
) -> None:
    """Run hook; log and ignore failures."""
    if not script or not script.strip():
        return
    try:
        _run_hook(script, cwd, timeout_ms, label)
    except subprocess.TimeoutExpired:
        log_fn(f"{label} hook timed out after {timeout_ms}ms")
    except Exception as e:
        log_fn(f"{label} hook error: {e}")


def create_for_issue(
    config: ServiceConfig,
    identifier: str,
    log_fn: Callable[[str], None] = print,
) -> Workspace:
    """
    Ensure workspace exists for issue. Run after_create only if created now.
    Invariant: path is under workspace root; key is sanitized.
    """
    root = config.workspace_root
    key = sanitize_workspace_key(identifier)
    path = os.path.join(root, key)
    root_abs = os.path.abspath(root)
    path_abs = os.path.abspath(path)
    if not path_abs.startswith(root_abs + os.sep) and path_abs != root_abs:
        raise ValueError(f"Workspace path must be under workspace root: {path_abs} vs {root_abs}")
    created_now = False
    if not os.path.isdir(path):
        if os.path.exists(path):
            raise FileExistsError(f"Workspace path exists but is not a directory: {path}")
        os.makedirs(path, exist_ok=True)
        created_now = True
    workspace = Workspace(path=path_abs, workspace_key=key, created_now=created_now)
    if created_now and config.hooks_after_create:
        _run_hook(
            config.hooks_after_create,
            path_abs,
            config.hooks_timeout_ms,
            "after_create",
        )
    return workspace


def run_before_run(config: ServiceConfig, workspace_path: str, log_fn: Callable[[str], None] = print) -> None:
    """Run before_run hook; failure aborts the attempt."""
    if not config.hooks_before_run:
        return
    _run_hook(
        config.hooks_before_run,
        workspace_path,
        config.hooks_timeout_ms,
        "before_run",
    )


def run_after_run(config: ServiceConfig, workspace_path: str, log_fn: Callable[[str], None] = print) -> None:
    """Run after_run hook; failure is logged and ignored."""
    _run_hook_best_effort(
        config.hooks_after_run,
        workspace_path,
        config.hooks_timeout_ms,
        "after_run",
        log_fn,
    )


def remove_workspace(
    config: ServiceConfig,
    workspace_path: str,
    log_fn: Callable[[str], None] = print,
) -> None:
    """Run before_remove (best effort), then remove directory."""
    root_abs = os.path.abspath(config.workspace_root)
    path_abs = os.path.abspath(workspace_path)
    if not path_abs.startswith(root_abs + os.sep) and path_abs != root_abs:
        raise ValueError(f"Workspace path must be under workspace root: {path_abs}")
    if config.hooks_before_remove:
        _run_hook_best_effort(
            config.hooks_before_remove,
            workspace_path,
            config.hooks_timeout_ms,
            "before_remove",
            log_fn,
        )
    if os.path.isdir(workspace_path):
        shutil.rmtree(workspace_path, ignore_errors=False)

"""Launcher UI backend: serves a simple page and can start API, web, and Symphony."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, PlainTextResponse

REPO_ROOT = Path(__file__).resolve().parent.parent
PROCESSES: dict[str, subprocess.Popen] = {}

app = FastAPI(title="Alpha-Kite Launcher")


def _read_html() -> str:
    path = Path(__file__).parent / "index.html"
    return path.read_text(encoding="utf-8")


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return _read_html()


@app.post("/start/api")
def start_api() -> dict:
    """Start the FastAPI trading backend (port 8000)."""
    if "api" in PROCESSES and PROCESSES["api"].poll() is None:
        return {"ok": True, "message": "API already running"}
    env = os.environ.copy()
    if (REPO_ROOT / ".venv").exists():
        python = REPO_ROOT / ".venv" / "bin" / "python3"
    else:
        python = "python3"
    proc = subprocess.Popen(
        [str(python), "apps/api/main.py"],
        cwd=REPO_ROOT,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    PROCESSES["api"] = proc
    return {"ok": True, "message": "API started", "pid": proc.pid}


@app.post("/start/web")
def start_web() -> dict:
    """Start the Next.js frontend (port 3000)."""
    if "web" in PROCESSES and PROCESSES["web"].poll() is None:
        return {"ok": True, "message": "Web app already running"}
    proc = subprocess.Popen(
        ["npm", "--prefix", "apps/web", "run", "dev"],
        cwd=REPO_ROOT,
        env=os.environ.copy(),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    PROCESSES["web"] = proc
    return {"ok": True, "message": "Web app started", "pid": proc.pid}


@app.post("/start/symphony")
def start_symphony() -> dict:
    """Start Symphony (Linear orchestration). Requires LINEAR_API_KEY in .env."""
    if "symphony" in PROCESSES and PROCESSES["symphony"].poll() is None:
        return {"ok": True, "message": "Symphony already running"}
    script = REPO_ROOT / "scripts" / "run-symphony.sh"
    if not script.exists():
        return {"ok": False, "message": "run-symphony.sh not found"}
    proc = subprocess.Popen(
        ["/bin/bash", str(script)],
        cwd=REPO_ROOT,
        env=os.environ.copy(),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    PROCESSES["symphony"] = proc
    return {"ok": True, "message": "Symphony started", "pid": proc.pid}


@app.get("/status")
def status() -> dict:
    """Return which processes are currently running."""
    return {
        "api": PROCESSES.get("api") is not None and PROCESSES["api"].poll() is None,
        "web": PROCESSES.get("web") is not None and PROCESSES["web"].poll() is None,
        "symphony": PROCESSES.get("symphony") is not None and PROCESSES["symphony"].poll() is None,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5050)

"""Optional HTTP server for dashboard and /api/v1/* (SPEC.md Section 13.7)."""
from __future__ import annotations

import json
import logging
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import TYPE_CHECKING
from urllib.parse import urlparse

if TYPE_CHECKING:
    from .orchestrator import Orchestrator

logger = logging.getLogger("symphony.server")


def _state_snapshot(orch: "Orchestrator") -> dict:
    with orch._lock:
        state = orch._state
        if not state:
            return {"running": [], "retrying": [], "codex_totals": {}, "rate_limits": None}
        return orch._snapshot(state)


class Handler(BaseHTTPRequestHandler):
    orchestrator: "Orchestrator | None" = None

    def log_message(self, format: str, *args) -> None:
        logger.info("%s - %s", self.address_string(), format % args)

    def _json(self, status: int, body: dict) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(body).encode("utf-8"))

    def _error(self, status: int, code: str, message: str) -> None:
        self._json(status, {"error": {"code": code, "message": message}})

    def do_GET(self) -> None:
        orch = Handler.orchestrator
        if not orch:
            self._error(503, "unavailable", "Orchestrator not set")
            return
        path = urlparse(self.path).path
        if path == "/" or path == "":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            snapshot = _state_snapshot(orch)
            html = _dashboard_html(snapshot)
            self.wfile.write(html.encode("utf-8"))
            return
        if path.startswith("/api/v1/"):
            if path == "/api/v1/state" or path == "/api/v1/state/":
                snapshot = _state_snapshot(orch)
                out = {
                    "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "counts": {"running": len(snapshot["running"]), "retrying": len(snapshot["retrying"])},
                    "running": snapshot["running"],
                    "retrying": snapshot["retrying"],
                    "codex_totals": snapshot["codex_totals"],
                    "rate_limits": snapshot["rate_limits"],
                }
                self._json(200, out)
                return
            # /api/v1/<issue_identifier>
            parts = path.strip("/").split("/")
            if len(parts) >= 3 and parts[0] == "api" and parts[1] == "v1":
                identifier = parts[2]
                snapshot = _state_snapshot(orch)
                for r in snapshot["running"]:
                    if r.get("issue_identifier") == identifier:
                        self._json(200, {"issue_identifier": identifier, "status": "running", "running": r})
                        return
                for r in snapshot["retrying"]:
                    if r.get("identifier") == identifier:
                        self._json(200, {"issue_identifier": identifier, "status": "retrying", "retry": r})
                        return
                self._error(404, "issue_not_found", f"Issue {identifier} not in running or retrying")
                return
        self._error(404, "not_found", "Not found")

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/v1/refresh" or path == "/api/v1/refresh/":
            orch = Handler.orchestrator
            if not orch:
                self._error(503, "unavailable", "Orchestrator not set")
                return
            threading.Timer(0.1, orch._tick).start()
            self._json(202, {"queued": True, "coalesced": False, "requested_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "operations": ["poll", "reconcile"]})
            return
        self._error(405, "method_not_allowed", "Method Not Allowed")


def _dashboard_html(snapshot: dict) -> str:
    running = snapshot.get("running", [])
    retrying = snapshot.get("retrying", [])
    totals = snapshot.get("codex_totals", {})
    return f"""<!DOCTYPE html>
<html>
<head><title>Symphony</title></head>
<body>
<h1>Symphony</h1>
<p>Running: {len(running)} | Retrying: {len(retrying)}</p>
<p>Tokens: input={totals.get('input_tokens', 0)} output={totals.get('output_tokens', 0)} total={totals.get('total_tokens', 0)} | seconds_running={totals.get('seconds_running', 0):.1f}</p>
<h2>Running</h2>
<pre>{json.dumps(running, indent=2)}</pre>
<h2>Retrying</h2>
<pre>{json.dumps(retrying, indent=2)}</pre>
</body>
</html>"""


def run(orch: "Orchestrator", port: int = 8080, host: str = "127.0.0.1") -> None:
    Handler.orchestrator = orch
    server = HTTPServer((host, port), Handler)
    logger.info("HTTP server listening on %s:%s", host, port)
    server.serve_forever()

"""CLI entrypoint and workflow file watch (SPEC.md Section 17.7, 6.2)."""
from __future__ import annotations

import argparse
import logging
import os
import sys
import threading
import time
from pathlib import Path

from .workflow_loader import load_workflow, WorkflowLoadError
from .orchestrator import Orchestrator


def main() -> int:
    parser = argparse.ArgumentParser(description="Symphony – orchestrate coding agents from Linear")
    parser.add_argument(
        "workflow_path",
        nargs="?",
        default="WORKFLOW.md",
        help="Path to WORKFLOW.md (default: ./WORKFLOW.md)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Optional HTTP server port for dashboard/API",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Verbose logging",
    )
    args = parser.parse_args()
    workflow_path = os.path.abspath(args.workflow_path)
    if not os.path.isfile(workflow_path):
        print(f"Error: workflow file not found: {workflow_path}", file=sys.stderr)
        return 1
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )
    workflow_path_holder: list[str] = [workflow_path]

    def get_path() -> str:
        return workflow_path_holder[0]

    def load(path: str):
        return load_workflow(path)

    orch = Orchestrator(get_workflow_path=get_path, load_workflow=load)
    try:
        orch.start()
    except WorkflowLoadError as e:
        print(f"Workflow error: {e.code} – {e.message}", file=sys.stderr)
        return 1
    except Exception as e:
        logging.exception("Startup failed")
        print(f"Startup failed: {e}", file=sys.stderr)
        return 1

    if args.port is not None:
        try:
            from . import server
            server_thread = threading.Thread(
                target=server.run,
                args=(orch,),
                kwargs={"port": args.port},
                daemon=True,
            )
            server_thread.start()
        except ImportError:
            logging.warning("Optional server module not available; --port ignored")

    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        pass
    finally:
        orch.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())

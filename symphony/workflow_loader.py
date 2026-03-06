"""Workflow loader: WORKFLOW.md with YAML front matter + prompt body (SPEC.md Section 5)."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .models import WorkflowDefinition


class WorkflowLoadError(Exception):
    """Raised when workflow file cannot be loaded or parsed."""
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(f"{code}: {message}")


def load_workflow(path: str | Path) -> WorkflowDefinition:
    """
    Load WORKFLOW.md from path.
    - If file starts with ---, parse until next --- as YAML; rest is prompt body.
    - If no front matter, entire file is prompt body and config is {}.
    """
    path = Path(path)
    if not path.exists():
        raise WorkflowLoadError("missing_workflow_file", f"Workflow file not found: {path}")
    raw = path.read_text(encoding="utf-8", errors="replace")

    config: dict[str, Any] = {}
    body = raw

    if raw.strip().startswith("---"):
        parts = raw.split("---", 2)
        if len(parts) < 3:
            raise WorkflowLoadError("workflow_parse_error", "Invalid YAML front matter (missing closing ---)")
        try:
            config = yaml.safe_load(parts[1])
        except yaml.YAMLError as e:
            raise WorkflowLoadError("workflow_parse_error", str(e))
        if config is None:
            config = {}
        if not isinstance(config, dict):
            raise WorkflowLoadError("workflow_front_matter_not_a_map", "Front matter must be a YAML map")
        body = parts[2]

    prompt_template = body.strip()
    return WorkflowDefinition(config=config, prompt_template=prompt_template or "You are working on an issue from Linear.")

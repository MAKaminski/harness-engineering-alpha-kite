"""Prompt template rendering with strict variable checking (SPEC.md Section 5.4, 12)."""
from __future__ import annotations

from typing import Any

from jinja2 import Environment, StrictUndefined, UndefinedError

from .models import Issue


def _issue_to_template_context(issue: Issue) -> dict[str, Any]:
    """Convert Issue to template-safe dict; keys as strings, nested preserved."""
    return {
        "id": issue.id,
        "identifier": issue.identifier,
        "title": issue.title,
        "description": issue.description or "",
        "priority": issue.priority,
        "state": issue.state,
        "branch_name": issue.branch_name or "",
        "url": issue.url or "",
        "labels": list(issue.labels),
        "blocked_by": [
            {"id": b.id, "identifier": b.identifier, "state": b.state}
            for b in issue.blocked_by
        ],
        "created_at": issue.created_at or "",
        "updated_at": issue.updated_at or "",
    }


def render_prompt(
    prompt_template: str,
    issue: Issue,
    attempt: int | None,
) -> str:
    """
    Render prompt with strict variable checking.
    Unknown variables or filters raise TemplateError (template_render_error).
    """
    env = Environment(undefined=StrictUndefined)
    try:
        t = env.from_string(prompt_template)
    except Exception as e:
        raise RuntimeError(f"template_parse_error: {e}") from e

    ctx = {"issue": _issue_to_template_context(issue), "attempt": attempt}
    try:
        return t.render(**ctx)
    except UndefinedError as e:
        raise RuntimeError(f"template_render_error: {e}") from e

#!/usr/bin/env bash
# Run Symphony to resolve open Linear issues (polls Linear, dispatches Codex agents per issue).
# Requires: LINEAR_API_KEY, LINEAR_PROJECT_SLUG (or set project_slug in WORKFLOW.md).
set -e
cd "$(dirname "$0")/.."

if [ -z "$LINEAR_API_KEY" ]; then
  echo "Error: LINEAR_API_KEY is not set." >&2
  echo "Set it with: export LINEAR_API_KEY=lin_api_..." >&2
  echo "Create a key at: https://linear.app/settings/api" >&2
  exit 1
fi

if [ -z "$LINEAR_PROJECT_SLUG" ]; then
  echo "Warning: LINEAR_PROJECT_SLUG is not set. Symphony will fail validation unless project_slug is set in WORKFLOW.md." >&2
  echo "For Alpha-Kite project use the slug from the project URL, e.g.:" >&2
  echo "  export LINEAR_PROJECT_SLUG=alpha-kite-f0ebf2d85f93" >&2
  echo "Or set tracker.project_slug in WORKFLOW.md to your Linear project slugId." >&2
fi

PYTHON=${PYTHON:-python3}
if ! command -v "$PYTHON" &>/dev/null; then
  echo "Error: $PYTHON not found." >&2
  exit 1
fi

# Optional: use venv if present
if [ -d ".venv" ]; then
  source .venv/bin/activate
fi

exec "$PYTHON" -m symphony.cli -v --port 8080

#!/usr/bin/env bash
# Run Symphony to resolve open Linear issues (polls Linear, dispatches Codex agents per issue).
# Requires: LINEAR_API_KEY, LINEAR_PROJECT_SLUG (or set project_slug in WORKFLOW.md).
# Loads .env and .env.local if present (both are gitignored — never commit secrets).
set -e
cd "$(dirname "$0")/.."

# Load env from gitignored files (optional)
for f in .env .env.local; do
  if [ -f "$f" ]; then
    set -a
    # shellcheck source=/dev/null
    source "$f"
    set +a
  fi
done

if [ -z "$LINEAR_API_KEY" ]; then
  echo "Error: LINEAR_API_KEY is not set." >&2
  echo "Set it with: export LINEAR_API_KEY=lin_api_..." >&2
  echo "Create a key at: https://linear.app/settings/api" >&2
  exit 1
fi

if [ -z "$LINEAR_PROJECT_ID" ] && [ -z "$LINEAR_PROJECT_SLUG" ]; then
  echo "Warning: Neither LINEAR_PROJECT_ID nor LINEAR_PROJECT_SLUG is set. Symphony will fail validation." >&2
  echo "Set one of them, e.g.:" >&2
  echo "  export LINEAR_PROJECT_ID=d77c9342-536d-41f4-9526-2fd38e65226c" >&2
  echo "  export LINEAR_PROJECT_SLUG=alpha-kite-f0ebf2d85f93" >&2
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

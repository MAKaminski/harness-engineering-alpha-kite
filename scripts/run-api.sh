#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

if [ -d ".venv" ]; then
  # shellcheck source=/dev/null
  source .venv/bin/activate
fi

python3 apps/api/main.py

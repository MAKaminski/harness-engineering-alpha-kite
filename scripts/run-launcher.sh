#!/usr/bin/env bash
# Start the launcher UI (port 5050). From the launcher you can start API, Web, Symphony and open Health / Market links.
set -e
cd "$(dirname "$0")/.."

if [ -d ".venv" ]; then
  # shellcheck source=/dev/null
  source .venv/bin/activate
fi

exec python3 launcher/app.py

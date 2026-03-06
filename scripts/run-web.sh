#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

npm --prefix apps/web run dev

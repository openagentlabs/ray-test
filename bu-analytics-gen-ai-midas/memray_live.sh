#!/usr/bin/env bash
# Connect memray live UI to the backend started by run_memray.py (default port 9999).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
PORT="${MIDAS_MEMRAY_PORT:-9999}"
cd "$ROOT/backend"
exec ./venv/bin/python -m memray live "$PORT"

#!/usr/bin/env bash
# Run MIDAS scenario test gate (backend pytest + frontend vitest).
# Usage:
#   bash _bmad-output/testing/run-scenario-tests.sh
#   bash _bmad-output/testing/run-scenario-tests.sh --backend-only [pytest args...]
#   bash _bmad-output/testing/run-scenario-tests.sh --frontend-only [vitest args...]
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
BACKEND_ONLY=false
FRONTEND_ONLY=false
EXTRA_ARGS=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --backend-only) BACKEND_ONLY=true; shift ;;
    --frontend-only) FRONTEND_ONLY=true; shift ;;
    *) EXTRA_ARGS+=("$1"); shift ;;
  esac
done

run_backend() {
  echo "=== Backend pytest ==="
  cd "$ROOT/backend"
  if ! python3 -c "import pytest" 2>/dev/null; then
    echo "Installing backend test deps..."
    python3 -m pip install -q -r requirements.txt
    if [[ -f requirements-dev.txt ]]; then
      python3 -m pip install -q -r requirements-dev.txt
    fi
  fi
  if [[ ${#EXTRA_ARGS[@]} -gt 0 ]]; then
    python3 -m pytest -q "${EXTRA_ARGS[@]}"
  else
    python3 -m pytest -q
  fi
}

run_frontend() {
  echo "=== Frontend Vitest ==="
  cd "$ROOT/frontend"
  if [[ ! -d node_modules ]]; then
    echo "Installing frontend deps (npm ci)..."
    npm ci
  fi
  if [[ ${#EXTRA_ARGS[@]} -gt 0 ]]; then
    npx vitest run "${EXTRA_ARGS[@]}"
  else
    npm run test
  fi
}

if $BACKEND_ONLY; then
  run_backend
elif $FRONTEND_ONLY; then
  run_frontend
else
  run_backend
  run_frontend
fi

echo "=== All requested test suites passed ==="

#!/usr/bin/env bash
# Regenerate pod_manager.v1 stubs from server protos. Requires dev deps (grpcio-tools).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PROTO_ROOT="$(cd "$ROOT/../server/proto" && pwd)"
cd "$ROOT"

run_protoc() {
  python -m grpc_tools.protoc -I "$PROTO_ROOT" \
    --python_out=src --grpc_python_out=src --pyi_out=src \
    pod_manager/v1/pool.proto
}

if command -v uv >/dev/null 2>&1; then
  uv sync --extra dev --quiet
  uv run python -m grpc_tools.protoc -I "$PROTO_ROOT" \
    --python_out=src --grpc_python_out=src --pyi_out=src \
    pod_manager/v1/pool.proto
elif [[ -x "$ROOT/.venv/bin/python" ]]; then
  "$ROOT/.venv/bin/python" -m pip install -q "grpcio-tools>=1.66" 2>/dev/null || true
  PATH="$ROOT/.venv/bin:$PATH" run_protoc
else
  echo "Install tooling: cd $ROOT && uv sync --extra dev" >&2
  exit 1
fi

echo "Client proto generation complete."

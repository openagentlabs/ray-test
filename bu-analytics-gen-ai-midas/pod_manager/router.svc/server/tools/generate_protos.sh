#!/usr/bin/env bash
# Regenerate Python gRPC/protobuf modules. Requires cloned API trees (one-time):
#   git clone --depth 1 --branch v1.34.1 https://github.com/envoyproxy/envoy.git /tmp/envoy-api
#   git clone --depth 1 https://github.com/googleapis/googleapis.git /tmp/googleapis
#   git clone --depth 1 https://github.com/cncf/xds.git /tmp/xds
#   git clone --depth 1 https://github.com/bufbuild/protoc-gen-validate /tmp/protoc-gen-validate
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PATH="$ROOT/.venv/bin:$PATH"
python -m grpc_tools.protoc -I proto --python_out=src --grpc_python_out=src --pyi_out=src \
  proto/pod_manager/v1/pool.proto
python -m grpc_tools.protoc \
  -I /tmp/envoy-api/api -I /tmp/googleapis -I /tmp/xds -I /tmp/protoc-gen-validate \
  --python_out=src --grpc_python_out=src --pyi_out=src \
  $(find /tmp/envoy-api/api/envoy/config/core/v3 -name '*.proto') \
  $(find /tmp/envoy-api/api/envoy/type/v3 -name '*.proto') \
  $(find /tmp/envoy-api/api/envoy/annotations -name '*.proto') \
  $(find /tmp/envoy-api/api/envoy/service/auth/v3 -name '*.proto') \
  /tmp/protoc-gen-validate/validate/validate.proto \
  /tmp/xds/xds/core/v3/context_params.proto \
  $(find /tmp/xds/udpa/annotations -name '*.proto')
echo "Proto generation complete."

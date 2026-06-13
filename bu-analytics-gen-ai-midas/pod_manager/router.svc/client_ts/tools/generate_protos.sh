#!/usr/bin/env bash
# Regenerate pod_manager.v1 stubs from server protos (ts-proto + grpc-js).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PROTO_ROOT="$(cd "$ROOT/../server/proto" && pwd)"
cd "$ROOT"

if [[ ! -d node_modules ]]; then
  echo "Run: cd $ROOT && npm install" >&2
  exit 1
fi

mkdir -p src/gen
npx protoc \
  --plugin=./node_modules/.bin/protoc-gen-ts_proto \
  --ts_proto_out=./src/gen \
  --ts_proto_opt=esModuleInterop=true,outputServices=grpc-js,useExactTypes=true,importSuffix=.js \
  -I "$PROTO_ROOT" \
  pod_manager/v1/pool.proto

echo "Client proto generation complete."

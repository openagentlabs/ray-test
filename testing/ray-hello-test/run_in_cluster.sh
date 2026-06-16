#!/usr/bin/env bash
# Run the live Ray demo inside the cluster head pod — the only supported entry point.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT="$ROOT/ray-hello-test/ray_live_demo.py"
NS="${RAY_NAMESPACE:-kuberay}"
CLUSTER="${RAY_CLUSTER_NAME:-ray-cluster}"

HEAD_POD="$(kubectl -n "$NS" get pods -l "ray.io/node-type=head,ray.io/cluster=$CLUSTER" \
  -o jsonpath='{.items[0].metadata.name}')"

if [[ -z "$HEAD_POD" ]]; then
  echo "ERROR: No Ray head pod found in namespace $NS (cluster=$CLUSTER)" >&2
  exit 1
fi

echo "Executing on cluster pod: $NS/$HEAD_POD (not local)"
kubectl cp "$SCRIPT" "$NS/$HEAD_POD:/tmp/ray_live_demo.py"
kubectl -n "$NS" exec "$HEAD_POD" -c ray-head -- \
  env RAY_HELLO_TEST_IN_CLUSTER=1 python /tmp/ray_live_demo.py "$@"

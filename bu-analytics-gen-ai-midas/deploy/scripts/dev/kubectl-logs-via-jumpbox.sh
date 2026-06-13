#!/usr/bin/env bash
# Fetch kubectl pod logs from the private EKS API via SSM on the jump box (AWS-RunShellScript).
#
# Usage (from repo root, valid AWS creds with ssm:SendCommand on the instance):
#   INSTANCE_ID=i-04231b2a8a4d98b63 ./deploy/scripts/dev/kubectl-logs-via-jumpbox.sh
#   REGION=us-east-1 MIDAS_ENV=dev CLUSTER=midas-eks-dev K8S_NAMESPACE=midas-apps INSTANCE_ID=i-... ./deploy/scripts/dev/kubectl-logs-via-jumpbox.sh
#
# Env: same as kubectl-validate-via-jumpbox.sh; LOG_LINES default 150.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
# shellcheck disable=SC1090
[[ -f "${ROOT}/deploy/.ci/terraform-env.sh" ]] && source "${ROOT}/deploy/.ci/terraform-env.sh" 2>/dev/null || true

REGION="${REGION:-${AWS_REGION:-us-east-1}}"
MIDAS_ENV="${MIDAS_ENV:-dev}"
CLUSTER="${CLUSTER:-${EKS_CLUSTER_NAME:-midas-eks-${MIDAS_ENV}}}"
K8S_NAMESPACE="${K8S_NAMESPACE:-midas-apps}"
INSTANCE_ID="${INSTANCE_ID:-i-04231b2a8a4d98b63}"
LOG_LINES="${LOG_LINES:-150}"

if ! aws sts get-caller-identity --region "$REGION" >/dev/null 2>&1; then
  echo "ERROR: AWS credentials invalid or expired (aws sts get-caller-identity failed)." >&2
  echo "  Run: aws sso login   # or refresh keys for your MIDAS profile, then retry." >&2
  exit 2
fi

if [[ -z "$INSTANCE_ID" || "$INSTANCE_ID" == "None" ]]; then
  echo "ERROR: Set INSTANCE_ID to the jump box EC2 id (e.g. i-04231b2a8a4d98b63)." >&2
  exit 1
fi

echo "Jump box ${INSTANCE_ID} (${REGION}), cluster ${CLUSTER}, ns ${K8S_NAMESPACE}, tail=${LOG_LINES}" >&2

TMP="$(mktemp)"
trap 'rm -f "$TMP"' EXIT

export _KL_REGION="$REGION" _KL_CLUSTER="$CLUSTER" _KL_NS="$K8S_NAMESPACE" _KL_LINES="$LOG_LINES"
python3 <<'PY' >"$TMP"
import json
import os
import shlex

region = os.environ["_KL_REGION"]
cluster = os.environ["_KL_CLUSTER"]
ns = os.environ["_KL_NS"]
lines = os.environ["_KL_LINES"]
R, C, N, L = shlex.quote(region), shlex.quote(cluster), shlex.quote(ns), shlex.quote(lines)

script = f"""#!/bin/bash
set -euxo pipefail
export AWS_DEFAULT_REGION={R}
export CLUSTER={C}
export NS={N}
export LOG_LINES={L}
command -v kubectl >/dev/null 2>&1 || {{ echo "ERROR: kubectl not found on jump box"; exit 1; }}
command -v aws >/dev/null 2>&1 || {{ echo "ERROR: aws not found on jump box"; exit 1; }}
KCFG="$(mktemp)"
export KUBECONFIG="$KCFG"
trap 'rm -f "$KCFG"' EXIT
aws eks update-kubeconfig --name "$CLUSTER" --region "$AWS_DEFAULT_REGION" --kubeconfig "$KUBECONFIG"
echo "=== kubectl get pods -n $NS -o wide ==="
kubectl get pods -n "$NS" -o wide || true
echo "=== kubectl get events -n $NS (recent) ==="
kubectl get events -n "$NS" --sort-by=.lastTimestamp 2>/dev/null | tail -40 || true
echo "=== logs (tail $LOG_LINES, all containers) per pod ==="
while read -r pod; do
  [[ -z "$pod" ]] && continue
  echo "----- POD $pod -----"
  kubectl logs -n "$NS" "$pod" --all-containers=true --tail="$LOG_LINES" 2>&1 || echo "(logs unavailable for $pod)"
done < <(kubectl get pods -n "$NS" -o name 2>/dev/null | sed 's|^pod/||' || true)
trap - EXIT
rm -f "$KCFG"
"""
print(json.dumps({"commands": [script]}))
PY

echo "Sending SSM RunShellScript..." >&2
CID="$(aws ssm send-command \
  --instance-ids "$INSTANCE_ID" \
  --document-name AWS-RunShellScript \
  --comment "MIDAS kubectl logs (${CLUSTER})" \
  --parameters "file://${TMP}" \
  --region "$REGION" \
  --query 'Command.CommandId' \
  --output text)"

echo "CommandId=${CID}" >&2

STATUS="Pending"
for _ in $(seq 1 120); do
  STATUS="$(aws ssm get-command-invocation \
    --command-id "$CID" \
    --instance-id "$INSTANCE_ID" \
    --region "$REGION" \
    --query 'Status' \
    --output text 2>/dev/null || echo Pending)"
  case "$STATUS" in
    Success|Failed|Cancelled|TimedOut) break ;;
    *) sleep 2 ;;
  esac
done

echo "SSM Status=${STATUS}" >&2

aws ssm get-command-invocation \
  --command-id "$CID" \
  --instance-id "$INSTANCE_ID" \
  --region "$REGION" \
  --query 'StandardOutputContent' \
  --output text 2>/dev/null || true

echo "--- stderr (remote) ---" >&2
REMOTE_ERR="$(aws ssm get-command-invocation \
  --command-id "$CID" \
  --instance-id "$INSTANCE_ID" \
  --region "$REGION" \
  --query 'StandardErrorContent' \
  --output text 2>/dev/null || true)"
printf '%s\n' "$REMOTE_ERR" >&2

[[ "$STATUS" == "Success" ]] || exit 1

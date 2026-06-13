#!/usr/bin/env bash
# Run kubectl against the private EKS API from the SSM jump box (AWS-RunShellScript), then validate results.
#
# Prerequisites:
#   - AWS CLI credentials on this machine (operator) with ec2:DescribeInstances, ssm:SendCommand,
#     ssm:GetCommandInvocation, and permission to read the jump box instance.
#   - Jump box: kubectl + AWS CLI v2, EKS access (see deploy/ecs-app/eks-jumpbox-access.tf).
#
# Usage:
#   ./kubectl-validate-via-jumpbox.sh
#   REGION=us-east-1 MIDAS_ENV=dev INSTANCE_ID=i-0123abcd ./kubectl-validate-via-jumpbox.sh
#
# Env:
#   REGION       - default us-east-1
#   MIDAS_ENV    - default dev (jump box tag Name=midas-<env>-ec2-ssm-test; cluster midas-eks-<env>)
#   CLUSTER      - override cluster name (default midas-eks-$MIDAS_ENV)
#   INSTANCE_ID  - optional; if unset, discover a running instance by Name tag
#   K8S_NAMESPACE - default midas-apps
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
# shellcheck disable=SC1090
[[ -f "${ROOT}/deploy/.ci/terraform-env.sh" ]] && source "${ROOT}/deploy/.ci/terraform-env.sh" 2>/dev/null || true

REGION="${REGION:-${AWS_REGION:-us-east-1}}"
MIDAS_ENV="${MIDAS_ENV:-dev}"
CLUSTER="${CLUSTER:-${EKS_CLUSTER_NAME:-midas-eks-${MIDAS_ENV}}}"
K8S_NAMESPACE="${K8S_NAMESPACE:-midas-apps}"
INSTANCE_ID="${INSTANCE_ID:-}"

usage() {
  sed -n '1,22p' "$0" | tail -n +2
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

if ! aws sts get-caller-identity --region "$REGION" >/dev/null 2>&1; then
  echo "ERROR: AWS credentials invalid or expired (aws sts get-caller-identity failed)." >&2
  echo "  Refresh credentials (e.g. aws sso login) and retry." >&2
  exit 2
fi

if [[ -z "$INSTANCE_ID" || "$INSTANCE_ID" == "None" ]]; then
  TAG_NAME="midas-${MIDAS_ENV}-ec2-ssm-test"
  echo "Discovering jump box by tag Name=${TAG_NAME}..." >&2
  INSTANCE_ID="$(aws ec2 describe-instances --region "$REGION" \
    --filters "Name=tag:Name,Values=${TAG_NAME}" "Name=instance-state-name,Values=running" \
    --query 'Reservations[0].Instances[0].InstanceId' --output text 2>/dev/null || echo "")"
fi

if [[ -z "$INSTANCE_ID" || "$INSTANCE_ID" == "None" ]]; then
  echo "ERROR: Could not find a running EC2 instance with Name=midas-${MIDAS_ENV}-ec2-ssm-test" >&2
  echo "  Set INSTANCE_ID=i-... or MIDAS_ENV to match your jump box tag / cluster." >&2
  exit 1
fi

echo "Using jump box ${INSTANCE_ID} (${REGION}), cluster ${CLUSTER}, ns ${K8S_NAMESPACE}" >&2

TMP="$(mktemp)"
trap 'rm -f "$TMP"' EXIT

export _KV_REGION="$REGION" _KV_CLUSTER="$CLUSTER" _KV_NS="$K8S_NAMESPACE"
python3 <<'PY' >"$TMP"
import json
import os
import shlex

region = os.environ["_KV_REGION"]
cluster = os.environ["_KV_CLUSTER"]
ns = os.environ["_KV_NS"]
R, C, N = shlex.quote(region), shlex.quote(cluster), shlex.quote(ns)

script = f"""#!/bin/bash
set -euxo pipefail
export AWS_DEFAULT_REGION={R}
export CLUSTER={C}
export NS={N}
command -v kubectl >/dev/null 2>&1 || {{ echo "ERROR: kubectl not found on jump box"; exit 1; }}
command -v aws >/dev/null 2>&1 || {{ echo "ERROR: aws not found on jump box"; exit 1; }}
# Isolated kubeconfig avoids inherited KUBECONFIG (e.g. multi-file) or stale entries that make kubectl use http://localhost:8080.
KCFG="$(mktemp)"
export KUBECONFIG="$KCFG"
cleanup_kcfg() {{ rm -f "$KCFG"; }}
trap cleanup_kcfg EXIT
aws eks update-kubeconfig --name "$CLUSTER" --region "$AWS_DEFAULT_REGION" --kubeconfig "$KUBECONFIG"
kubectl cluster-info --request-timeout=20s
echo "=== kubectl get pods -n $NS -o wide ==="
kubectl get pods -n "$NS" -o wide
echo "=== kubectl get deploy -n $NS ==="
kubectl get deploy -n "$NS" -o wide
echo "=== rollout status (each deployment) ==="
for d in midas-web-frontend-svc midas-api-backend-svc midas-graph-svc; do
  if kubectl get "deployment/$d" -n "$NS" >/dev/null 2>&1; then
    kubectl rollout status "deployment/$d" -n "$NS" --timeout=240s
  else
    echo "WARN: deployment/$d not found in ns $NS (skip)"
  fi
done
echo "=== recent events ==="
kubectl get events -n "$NS" --sort-by=.lastTimestamp 2>/dev/null | tail -35 || true
BAD="$(kubectl get pods -n "$NS" --no-headers 2>/dev/null | grep -E 'ImagePullBackOff|CrashLoopBackOff|ErrImagePull|CreateContainerConfigError|OOMKilled|Evicted' || true)"
if [[ -n "$BAD" ]]; then
  echo "VALIDATION_FAIL: unhealthy pod rows:"
  echo "$BAD"
  exit 1
fi
NOT_RUNNING="$(kubectl get pods -n "$NS" --no-headers 2>/dev/null | awk '$3!="Running" && $3!="Completed" {{print}}' || true)"
if [[ -n "$NOT_RUNNING" ]]; then
  echo "VALIDATION_FAIL: pods not in Running/Completed:"
  echo "$NOT_RUNNING"
  exit 1
fi
echo "VALIDATION_OK: all pods Running or Completed; deployments available."
trap - EXIT
rm -f "$KCFG"
"""
print(json.dumps({"commands": [script]}))
PY

echo "Sending SSM RunShellScript..." >&2
CID="$(aws ssm send-command \
  --instance-ids "$INSTANCE_ID" \
  --document-name AWS-RunShellScript \
  --comment "MIDAS kubectl validate (${CLUSTER})" \
  --parameters "file://${TMP}" \
  --region "$REGION" \
  --query 'Command.CommandId' \
  --output text)"

echo "CommandId=${CID}" >&2

STATUS="Pending"
for _ in $(seq 1 90); do
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

OUT="$(aws ssm get-command-invocation \
  --command-id "$CID" \
  --instance-id "$INSTANCE_ID" \
  --region "$REGION" \
  --query 'StandardOutputContent' \
  --output text 2>/dev/null || true)"
ERR="$(aws ssm get-command-invocation \
  --command-id "$CID" \
  --instance-id "$INSTANCE_ID" \
  --region "$REGION" \
  --query 'StandardErrorContent' \
  --output text 2>/dev/null || true)"

printf '%s\n' "$OUT"
if [[ -n "$ERR" ]]; then
  echo "--- stderr (remote) ---" >&2
  printf '%s\n' "$ERR" >&2
fi

if [[ "$STATUS" != "Success" ]]; then
  echo "ERROR: SSM command did not succeed (status=$STATUS)." >&2
  exit 1
fi

if ! printf '%s' "$OUT" | grep -q 'VALIDATION_OK'; then
  echo "ERROR: remote script did not print VALIDATION_OK (see stdout above)." >&2
  exit 1
fi

echo "---" >&2
echo "Local check: SSM Success + VALIDATION_OK present." >&2

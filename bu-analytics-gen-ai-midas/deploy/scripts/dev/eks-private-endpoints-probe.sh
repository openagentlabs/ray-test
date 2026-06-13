#!/usr/bin/env bash
# Full private-EKS (EC2 nodes + Fargate) regional endpoint DNS/HTTPS probe via SSM.
# Region fixed us-east-1 per MIDAS deploy conventions.
#
# First 11 hosts match the "core" checklist (same as eks-ssm-endpoint-check.sh); then extended services.
# For core-only: ./eks-ssm-endpoint-check.sh
# TRAFFIC_LIGHT=1 ./eks-private-endpoints-probe.sh  # skill-format report
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REGION="${REGION:-us-east-1}"
INSTANCE_ID="${INSTANCE_ID:-i-047d7dcb9806a494c}"

TMP="$(mktemp)"
trap 'rm -f "$TMP"' EXIT

python3 <<'PY' >"$TMP"
import json

# Hostnames align with AWS guidance for private EKS clusters (interface + S3 API hostname).
# See: https://docs.aws.amazon.com/eks/latest/userguide/private-clusters.html
script = r"""#!/bin/bash
set +e
HOSTS=(
  eks.us-east-1.amazonaws.com
  eks.us-east-1.api.aws
  eks-auth.us-east-1.api.aws
  sts.us-east-1.amazonaws.com
  ec2.us-east-1.amazonaws.com
  api.ecr.us-east-1.amazonaws.com
  dkr.ecr.us-east-1.amazonaws.com
  s3.us-east-1.amazonaws.com
  elasticloadbalancing.us-east-1.amazonaws.com
  logs.us-east-1.amazonaws.com
  ssm.us-east-1.amazonaws.com
  autoscaling.us-east-1.amazonaws.com
  kms.us-east-1.amazonaws.com
  monitoring.us-east-1.amazonaws.com
  ssmmessages.us-east-1.amazonaws.com
  ec2messages.us-east-1.amazonaws.com
  s3-control.us-east-1.amazonaws.com
  secretsmanager.us-east-1.amazonaws.com
  acm.us-east-1.amazonaws.com
  rds.us-east-1.amazonaws.com
  rds-data.us-east-1.amazonaws.com
  elasticache.us-east-1.amazonaws.com
)
for h in "${HOSTS[@]}"; do
  echo "=== $h ==="
  nslookup "$h" 2>&1 | head -24
  curl -sS -o /dev/null -w 'http_code=%{http_code} connect=%{time_connect}s\n' --connect-timeout 10 --max-time 15 "https://$h/" 2>&1
  echo ""
done
"""
print(json.dumps({"commands": [script]}))
PY

echo "Sending SSM RunShellScript to ${INSTANCE_ID} (${REGION})..." >&2
CID="$(aws ssm send-command \
  --instance-ids "$INSTANCE_ID" \
  --document-name AWS-RunShellScript \
  --comment "EKS private full endpoint probe (core 11 + extended)" \
  --parameters "file://${TMP}" \
  --region "$REGION" \
  --query 'Command.CommandId' \
  --output text)"

echo "CommandId=${CID}" >&2

STATUS="Pending"
for _ in $(seq 1 60); do
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

echo "Status=${STATUS}" >&2
if [[ "$STATUS" != "Success" ]]; then
  aws ssm get-command-invocation \
    --command-id "$CID" \
    --instance-id "$INSTANCE_ID" \
    --region "$REGION" \
    --query '[StandardErrorContent, StandardOutputContent]' \
    --output text
  exit 1
fi

RAW="$(aws ssm get-command-invocation \
  --command-id "$CID" \
  --instance-id "$INSTANCE_ID" \
  --region "$REGION" \
  --query 'StandardOutputContent' \
  --output text)"

if [[ "${TRAFFIC_LIGHT:-0}" == "1" ]]; then
  printf '%s' "$RAW" | PROBE_INSTANCE_ID="$INSTANCE_ID" SSM_COMMAND_ID="$CID" PROBE_REGION="$REGION" \
    python3 "$SCRIPT_DIR/eks-probe-to-traffic-light.py"
else
  printf '%s' "$RAW"
fi

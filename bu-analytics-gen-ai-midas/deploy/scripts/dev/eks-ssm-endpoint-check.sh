#!/usr/bin/env bash
# Core EKS/VPC connectivity probe (11 regional hosts, us-east-1): nslookup + curl https://$host/
# Run from your workstation via SSM SendCommand - no Session Manager plugin required.
#
# Hosts (traffic-light expectations when PrivateLink is partial - see docs):
#   eks / eks.api.aws / eks-auth - often 🟡 DNS public; .api.aws paths may 🔴 HTTPS (TLS reset)
#   sts, s3, elb, logs, ssm - usually 🟡 DNS public, 🟢 HTTPS
#   ec2, api.ecr, dkr.ecr - often 🟢 DNS private 10.72.x; dkr may 🟡 HTTPS (cert SAN)
#
# Usage: REGION=us-east-1 INSTANCE_ID=i-... ./eks-ssm-endpoint-check.sh
#        TRAFFIC_LIGHT=1 ./eks-ssm-endpoint-check.sh   # print skill-format report (stdin to eks-probe-to-traffic-light.py)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REGION="${REGION:-us-east-1}"
INSTANCE_ID="${INSTANCE_ID:-i-047d7dcb9806a494c}"

TMP="$(mktemp)"
trap 'rm -f "$TMP"' EXIT

python3 <<'PY' >"$TMP"
import json

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
  --comment "EKS core 11-host DNS/HTTPS probe" \
  --parameters "file://${TMP}" \
  --region "$REGION" \
  --query 'Command.CommandId' \
  --output text)"

echo "CommandId=${CID}" >&2

STATUS="Pending"
for _ in $(seq 1 45); do
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

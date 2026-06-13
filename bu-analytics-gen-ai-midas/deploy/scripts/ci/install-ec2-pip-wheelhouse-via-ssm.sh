#!/usr/bin/env bash
# Queue SSM Run Command on an EC2 instance to:
#   1. Sync pip wheelhouse from s3://<bucket>/pip-packages/   -> /tmp/pip-packages/
#   2. Sync app code     from s3://<bucket>/midas-ec2-mt-test/app/  -> /ec2-mt-test/
#   3. Sync AWS CLI v2   from s3://<bucket>/midas-ec2-mt-test/awscli/ -> install offline
#   4. Recreate /ec2-mt-test/.venv from wheelhouse
#   5. Run full import smoke tests (top-level + pipeline submodules)
#   6. Write /ec2-mt-test/.midas-ec2-mt-test-manifest.json
#
# Component tag: midas:component=ec2-mt-test  (bundle_id: MIDAS_EC2_MT_TEST)
#
# Run from a host with AWS credentials (Jenkins agent after Checkout, or laptop with SSO).
#
# Usage:
#   ./deploy/scripts/ci/install-ec2-pip-wheelhouse-via-ssm.sh <instance-id> [aws-region]
#
# Requires: aws CLI, instance online in SSM, IAM on the instance allowing s3:GetObject on
#   pip-packages/* and midas-ec2-mt-test/* in the configured S3 bucket.

set -euo pipefail

INSTANCE_ID="${1:?usage: $0 <instance-id> [region]}"
REGION="${2:-${AWS_REGION:-us-east-1}}"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
PARAM_FILE="${ROOT}/deploy/scripts/ci/ssm-ec2-pip-wheelhouse-install.parameters.json"

if [[ ! -f "$PARAM_FILE" ]]; then
  echo "ERROR: missing $PARAM_FILE" >&2
  exit 1
fi

CID=$(aws ssm send-command \
  --region "$REGION" \
  --instance-ids "$INSTANCE_ID" \
  --document-name "AWS-RunShellScript" \
  --comment "MIDAS: offline pip venv from S3 wheelhouse" \
  --timeout-seconds 7200 \
  --parameters "file://${PARAM_FILE}" \
  --output text \
  --query 'Command.CommandId')

echo "[INFO] SSM CommandId=$CID"

for _i in $(seq 1 720); do
  ST=$(aws ssm get-command-invocation --region "$REGION" --command-id "$CID" --instance-id "$INSTANCE_ID" --query Status --output text 2>/dev/null || echo Unknown)
  case "$ST" in
    Success)
      RC=$(aws ssm get-command-invocation --region "$REGION" --command-id "$CID" --instance-id "$INSTANCE_ID" --query ResponseCode --output text)
      echo "[INFO] SSM finished Success response_code=$RC"
      if [[ "$RC" != "0" ]]; then
        aws ssm get-command-invocation --region "$REGION" --command-id "$CID" --instance-id "$INSTANCE_ID" --output text --query StandardErrorContent
        exit 1
      fi
      exit 0
      ;;
    Failed|Cancelled|TimedOut)
      echo "[ERROR] SSM Status=$ST" >&2
      aws ssm get-command-invocation --region "$REGION" --command-id "$CID" --instance-id "$INSTANCE_ID" --output text --query StandardErrorContent >&2 || true
      exit 1
      ;;
  esac
  sleep 10
done

echo "[ERROR] SSM command did not finish within polling window" >&2
exit 1

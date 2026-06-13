#!/usr/bin/env bash
# Force AWS_REGION / AWS_DEFAULT_REGION / AWS_SECRETS_MANAGER_REGION in the
# midas-{env}-us-east-1/app Secrets Manager secret to a valid literal region string.
# Use when pods show boto errors like secretsmanager.dXMtZWFzdC0x.amazonaws.com (base64
# pasted into region env). Idempotent if values are already correct.
#
# Also normalizes AWS_RDS_POSTGRES_HOST and AWS_RDS_POSTGRES_PORT when provided:
# Use when host/port are missing from SM (e.g. fresh account, Terraform seed ran before
# the fix, or populate-secrets.sh clobbered the values). Idempotent if already correct.
#
# Usage:
#   ./deploy/scripts/ci/fix-sm-app-aws-region-keys.sh [ENVIRONMENT]
# Env:
#   AWS_REGION            (default us-east-1)
#   TARGET_AWS_REGION     (default same as AWS_REGION)
#   RDS_HOST              RDS endpoint to set in AWS_RDS_POSTGRES_HOST (skip if empty)
#   RDS_PORT              RDS port to set in AWS_RDS_POSTGRES_PORT     (default 5432, skip if empty)
set -euo pipefail

ENVIRONMENT="${1:-dev}"
REGION="${AWS_REGION:-us-east-1}"
TARGET="${TARGET_AWS_REGION:-$REGION}"
SECRET_NAME="midas-${ENVIRONMENT}-${REGION}/app"
RDS_HOST="${RDS_HOST:-}"
RDS_PORT="${RDS_PORT:-}"

echo "=== Fixing region keys in ${SECRET_NAME} (target region: ${TARGET}) ==="
[[ -n "${RDS_HOST}" ]] && echo "    also setting AWS_RDS_POSTGRES_HOST=${RDS_HOST}"
[[ -n "${RDS_PORT}" ]] && echo "    also setting AWS_RDS_POSTGRES_PORT=${RDS_PORT}"

CUR="$(aws secretsmanager get-secret-value \
  --secret-id "${SECRET_NAME}" \
  --region "${REGION}" \
  --query SecretString \
  --output text)"

NEW="$(python3 -c "
import json, sys
d = json.loads(sys.argv[1])
target_region = sys.argv[2]
rds_host = sys.argv[3]
rds_port = sys.argv[4]

# Force literal region strings (never base64).
for k in ('AWS_REGION', 'AWS_DEFAULT_REGION', 'AWS_SECRETS_MANAGER_REGION'):
    d[k] = target_region

# Set RDS connection keys when operator provides them (empty string = skip).
# These keys are required by the Python secrets loader when the RDS-managed secret
# (after rotation) contains only username/password.
if rds_host:
    d['AWS_RDS_POSTGRES_HOST'] = rds_host
if rds_port:
    d['AWS_RDS_POSTGRES_PORT'] = rds_port

print(json.dumps(d))
" "${CUR}" "${TARGET}" "${RDS_HOST}" "${RDS_PORT}")"

aws secretsmanager put-secret-value \
  --secret-id "${SECRET_NAME}" \
  --region "${REGION}" \
  --secret-string "${NEW}"

echo "=== Done. Re-sync K8s (helm-deploy-releases.sh or terraform apply) and rollout API pods. ==="

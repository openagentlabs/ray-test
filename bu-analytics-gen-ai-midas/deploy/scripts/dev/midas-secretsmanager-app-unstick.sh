#!/usr/bin/env bash
# -----------------------------------------------------------------------------
# Fix "secret ... already scheduled for deletion" or prepare for terraform import
# when midas-<env>-<region>/app exists in AWS but Terraform apply tries CreateSecret.
#
# Prerequisites: aws CLI, credentials for the workload account, deploy/ecs-app inited.
#
# Usage:
#   ./deploy/scripts/midas-secretsmanager-app-unstick.sh restore
#   ./deploy/scripts/midas-secretsmanager-app-unstick.sh restore-and-delete   # frees name; next apply creates new secret
#   SECRET_ID=midas-uat-us-east-1/app ./deploy/scripts/midas-secretsmanager-app-unstick.sh restore
# -----------------------------------------------------------------------------

set -euo pipefail

REGION="${AWS_REGION:-us-east-1}"
SECRET_ID="${SECRET_ID:-midas-dev-us-east-1/app}"
MODE="${1:-restore}"

describe() {
  aws secretsmanager describe-secret --secret-id "${SECRET_ID}" --region "${REGION}" 2>/dev/null || true
}

case "${MODE}" in
  restore)
    echo "Describing ${SECRET_ID} (${REGION})..."
    if ! describe | grep -q '"ARN"'; then
      echo "Secret not found or not accessible. Nothing to restore."
      exit 0
    fi
    DELETED=$(aws secretsmanager describe-secret --secret-id "${SECRET_ID}" --region "${REGION}" --query 'DeletedDate' --output text 2>/dev/null || echo "None")
    if [[ "${DELETED}" != "None" && -n "${DELETED}" ]]; then
      echo "Secret is scheduled for deletion (DeletedDate=${DELETED}). Restoring..."
      aws secretsmanager restore-secret --secret-id "${SECRET_ID}" --region "${REGION}"
      echo "Restore requested. Wait a few seconds, then import into Terraform:"
    else
      echo "Secret is active (not scheduled for deletion). Import if state is missing:"
    fi
    echo "  cd deploy/ecs-app   # after terraform init with Jenkins backend config"
    echo "  # Pass the same -var-file / -var as terraform plan (aws_account_id, environment, ...):"
    echo "  terraform import -var-file=tfvars/midas-cross-network-db-access.tfvars \\"
    echo "    -var 'aws_account_id=...' -var 'environment=...' -var 'terraform_state_bucket=...' \\"
    echo "    'module.secretsmanager.aws_secretsmanager_secret.app' '${SECRET_ID}'"
    ;;
  restore-and-delete)
    echo "Restoring (if needed) then force-deleting ${SECRET_ID} so the next apply can CreateSecret."
    DELETED=$(aws secretsmanager describe-secret --secret-id "${SECRET_ID}" --region "${REGION}" --query 'DeletedDate' --output text 2>/dev/null || echo "None")
    if [[ "${DELETED}" != "None" && -n "${DELETED}" ]]; then
      aws secretsmanager restore-secret --secret-id "${SECRET_ID}" --region "${REGION}"
      sleep 3
    fi
    aws secretsmanager delete-secret --secret-id "${SECRET_ID}" --force-delete-without-recovery --region "${REGION}"
    echo "Done. Run a fresh terraform plan/apply; no import needed for create."
    ;;
  *)
    echo "Usage: $0 restore | restore-and-delete"
    echo "Optional env: SECRET_ID (default ${SECRET_ID}), AWS_REGION (default ${REGION})"
    exit 1
    ;;
esac

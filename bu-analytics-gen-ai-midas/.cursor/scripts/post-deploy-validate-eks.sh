#!/usr/bin/env bash
# Post-deploy: cluster + node group + node Ready + optional SSM kubelet logs.
# Run from a host with network access to the *private* EKS API endpoint.
# Usage:
#   export AWS_REGION=us-east-1
#   export CLUSTER_NAME=midas-eks-dev
#   export WAIT_MINUTES=25
#   export SSM_INSTANCE_IDS="i-abc,i-def"   # optional
#   ./post-deploy-validate-eks.sh
set -uo pipefail

REGION="${AWS_REGION:-us-east-1}"
CLUSTER_NAME="${CLUSTER_NAME:?Set CLUSTER_NAME to the EKS cluster name (Terraform output eks_cluster_name)}"
NODEGROUP_NAME="${NODEGROUP_NAME:-${CLUSTER_NAME}-ng}"
WAIT_MINUTES="${WAIT_MINUTES:-25}"
POLL_SECS="${POLL_SECS:-45}"
DESIRED_READY_NODES="${DESIRED_READY_NODES:-2}"

echo "=== Post-deploy EKS validation (cluster=${CLUSTER_NAME}, region=${REGION}) ==="

echo "-- describe-cluster"
aws eks describe-cluster --region "${REGION}" --name "${CLUSTER_NAME}" \
  --query 'cluster.{status:status,version:version,endpoint:endpoint}' --output table

echo "-- describe-nodegroup ${NODEGROUP_NAME}"
aws eks describe-nodegroup --region "${REGION}" --cluster-name "${CLUSTER_NAME}" --nodegroup-name "${NODEGROUP_NAME}" \
  --query 'nodegroup.{status:status,health:health,scalingConfig:scalingConfig,instanceTypes:instanceTypes}' --output table

if ! command -v kubectl >/dev/null 2>&1; then
  echo "WARN: kubectl not found; skip node Ready check." >&2
  exit 0
fi

echo "-- update-kubeconfig"
aws eks update-kubeconfig --region "${REGION}" --name "${CLUSTER_NAME}"

deadline=$((SECONDS + WAIT_MINUTES * 60))
ready=0
while [[ ${SECONDS} -lt ${deadline} ]]; do
  kubectl get nodes -o wide 2>/dev/null || true
  ready=$(kubectl get nodes --no-headers 2>/dev/null | awk '$2=="Ready"{c++} END{print c+0}')
  echo "Ready nodes: ${ready} (want ${DESIRED_READY_NODES})"
  if [[ "${ready}" -ge "${DESIRED_READY_NODES}" ]]; then
    echo "=== Kubernetes reports enough Ready nodes ==="
    break
  fi
  echo "Sleep ${POLL_SECS}s ..."
  sleep "${POLL_SECS}"
done

set -e
if [[ "${ready}" -lt "${DESIRED_READY_NODES}" ]]; then
  echo "FAIL: fewer than ${DESIRED_READY_NODES} Ready nodes within ${WAIT_MINUTES} minutes. Check node group health, kubelet logs, SGs, endpoints." >&2
  exit 1
fi

echo "-- CloudWatch log group (recent streams)"
aws logs describe-log-streams --region "${REGION}" \
  --log-group-name "/aws/eks/${CLUSTER_NAME}/cluster" \
  --order-by LastEventTime --descending --max-items 3 --output table || echo "WARN: no log streams yet or no access"

if [[ -n "${SSM_INSTANCE_IDS:-}" ]]; then
  echo "-- SSM kubelet snippet (requires ssm:SendCommand on instances)"
  IFS=',' read -ra IDS <<< "${SSM_INSTANCE_IDS// /}"
  for i in "${IDS[@]}"; do
    [[ -z "${i}" ]] && continue
    echo "---- instance ${i}"
    cid=$(aws ssm send-command --region "${REGION}" \
      --instance-ids "${i}" \
      --document-name "AWS-RunShellScript" \
      --parameters 'commands=["journalctl -u kubelet -n 80 --no-pager"]' \
      --query 'Command.CommandId' --output text)
    sleep 8
    aws ssm get-command-invocation --region "${REGION}" --command-id "${cid}" --instance-id "${i}" \
      --query '{Status:Status,Stdout:StandardOutputContent}' --output text
  done
fi

echo "=== Post-deploy validation complete ==="

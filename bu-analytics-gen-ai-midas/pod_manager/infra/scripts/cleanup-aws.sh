#!/usr/bin/env bash
# Remove leftover AWS resources for pod_manager dev (post-terraform destroy).
# Safe to re-run; skips resources that are already gone.
set -euo pipefail

REGION="${AWS_REGION:-us-east-1}"
CLUSTER="${EKS_CLUSTER_NAME:-dev-pod-manager}"
ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"

echo "Account: ${ACCOUNT_ID}  Region: ${REGION}"
echo "Cluster: ${CLUSTER}"
echo

delete_ecr_repos() {
  local repos=(router-svc login-pod envoy-router backend-pool-node)
  for repo in "${repos[@]}"; do
    if ! aws ecr describe-repositories --repository-names "$repo" --region "$REGION" &>/dev/null; then
      echo "[ecr] skip (missing): $repo"
      continue
    fi
    echo "[ecr] empty + delete: $repo"
    local ids
    ids="$(aws ecr list-images --repository-name "$repo" --region "$REGION" \
      --query 'imageIds' --output json 2>/dev/null || echo '[]')"
    if [[ "$ids" != "[]" && -n "$ids" ]]; then
      aws ecr batch-delete-image --repository-name "$repo" --region "$REGION" \
        --image-ids "$ids" >/dev/null || true
    fi
    aws ecr delete-repository --repository-name "$repo" --region "$REGION" --force
    echo "[ecr] deleted: $repo"
  done
}

delete_log_groups() {
  local groups=(
    "/aws/eks/${CLUSTER}/cluster"
    "/aws/eks/${CLUSTER}"
  )
  for lg in "${groups[@]}"; do
    if ! aws logs describe-log-groups --log-group-name-prefix "$lg" --region "$REGION" \
      --query 'logGroups[0].logGroupName' --output text 2>/dev/null | grep -q .; then
      echo "[logs] skip (missing): $lg"
      continue
    fi
    for name in $(aws logs describe-log-groups --log-group-name-prefix "$lg" --region "$REGION" \
      --query 'logGroups[].logGroupName' --output text); do
      echo "[logs] delete: $name"
      aws logs delete-log-group --log-group-name "$name" --region "$REGION"
    done
  done
}

delete_iam_role_and_policies() {
  local roles=(
    "${CLUSTER}-alb-controller"
    "${CLUSTER}-cluster-"
    "dev-pod-manager-irsa"
    "${CLUSTER}"
  )
  # Delete known exact roles from terraform naming
  local exact_roles=(
    "dev-pod-manager-irsa"
    "dev-pod-manager-alb-controller"
  )
  for role in "${exact_roles[@]}"; do
    if ! aws iam get-role --role-name "$role" &>/dev/null; then
      echo "[iam] skip role (missing): $role"
      continue
    fi
    echo "[iam] detach + delete role: $role"
    for arn in $(aws iam list-attached-role-policies --role-name "$role" \
      --query 'AttachedPolicies[].PolicyArn' --output text 2>/dev/null); do
      aws iam detach-role-policy --role-name "$role" --policy-arn "$arn" || true
    done
    for inline in $(aws iam list-role-policies --role-name "$role" \
      --query 'PolicyNames[]' --output text 2>/dev/null); do
      aws iam delete-role-policy --role-name "$role" --policy-name "$inline" || true
    done
    aws iam delete-role --role-name "$role" || true
  done

  # Cluster-scoped roles from EKS module (prefix match)
  while read -r role; do
    [[ -z "$role" ]] && continue
    [[ "$role" != *"${CLUSTER}"* ]] && continue
    echo "[iam] delete EKS role: $role"
    for arn in $(aws iam list-attached-role-policies --role-name "$role" \
      --query 'AttachedPolicies[].PolicyArn' --output text 2>/dev/null); do
      aws iam detach-role-policy --role-name "$role" --policy-arn "$arn" || true
    done
    for inline in $(aws iam list-role-policies --role-name "$role" \
      --query 'PolicyNames[]' --output text 2>/dev/null); do
      aws iam delete-role-policy --role-name "$role" --policy-name "$inline" || true
    done
    aws iam delete-role --role-name "$role" || true
  done < <(aws iam list-roles --query "Roles[?contains(RoleName, '${CLUSTER}')].RoleName" --output text | tr '\t' '\n')

  while read -r arn; do
    [[ -z "$arn" ]] && continue
    local name
    name="$(basename "$arn")"
    echo "[iam] delete policy: $name"
    aws iam delete-policy --policy-arn "$arn" || true
  done < <(aws iam list-policies --scope Local \
    --query "Policies[?contains(PolicyName, '${CLUSTER}')].Arn" --output text | tr '\t' '\n')
}

delete_eks_cluster() {
  if ! aws eks describe-cluster --name "$CLUSTER" --region "$REGION" &>/dev/null; then
    echo "[eks] skip (missing): $CLUSTER"
    return
  fi
  echo "[eks] delete nodegroups for $CLUSTER"
  for ng in $(aws eks list-nodegroups --cluster-name "$CLUSTER" --region "$REGION" \
    --query 'nodegroups[]' --output text); do
    echo "[eks] delete nodegroup: $ng"
    aws eks delete-nodegroup --cluster-name "$CLUSTER" --nodegroup-name "$ng" --region "$REGION"
    aws eks wait nodegroup-deleted --cluster-name "$CLUSTER" --nodegroup-name "$ng" --region "$REGION"
  done
  echo "[eks] delete cluster: $CLUSTER"
  aws eks delete-cluster --name "$CLUSTER" --region "$REGION"
  aws eks wait cluster-deleted --name "$CLUSTER" --region "$REGION"
}

report_kms_pending() {
  while read -r arn; do
    [[ -z "$arn" ]] && continue
    local key_id="${arn##*/}"
    local state
    state="$(aws kms describe-key --key-id "$key_id" --region "$REGION" \
      --query 'KeyMetadata.KeyState' --output text)"
    echo "[kms] ${key_id} state=${state}"
    if [[ "$state" == "Enabled" ]]; then
      echo "[kms] scheduling deletion (7 day minimum) for ${key_id}"
      aws kms schedule-key-deletion --key-id "$key_id" --pending-window-in-days 7 --region "$REGION"
    fi
  done < <(aws resourcegroupstaggingapi get-resources --region "$REGION" \
    --tag-filters Key=Project,Values=pod-manager \
    --resource-type-filters kms:key \
    --query 'ResourceTagMappingList[].ResourceARN' --output text | tr '\t' '\n')
}

delete_k8s_load_balancers() {
  while read -r arn; do
    [[ -z "$arn" ]] && continue
    echo "[elb] delete: $arn"
    aws elbv2 delete-load-balancer --load-balancer-arn "$arn" --region "$REGION"
  done < <(aws elbv2 describe-load-balancers --region "$REGION" --output json | python3 -c "
import json,sys
for lb in json.load(sys.stdin).get('LoadBalancers',[]):
    n=lb['LoadBalancerName'].lower()
    if 'routing' in n or 'pod' in n or 'router' in n or 'envoy' in n or 'k8s-routing' in n:
        print(lb['LoadBalancerArn'])
")
}

delete_ecr_repos
delete_log_groups
delete_iam_role_and_policies
delete_eks_cluster
delete_k8s_load_balancers
report_kms_pending

echo
echo "Cleanup pass complete. Re-check:"
echo "  aws resourcegroupstaggingapi get-resources --region ${REGION} --tag-filters Key=Project,Values=pod-manager"

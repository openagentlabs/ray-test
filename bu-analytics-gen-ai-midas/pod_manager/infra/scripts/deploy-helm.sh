#!/usr/bin/env bash
# Deploy routing-tier Helm release to EKS.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TF_DIR="${ROOT}/infra/terraform/environments/dev"
CHART_DIR="${ROOT}/infra/helm/routing-tier"
NAMESPACE="${K8S_NAMESPACE:-routing}"
RELEASE="${HELM_RELEASE:-routing-tier}"
TAG="${IMAGE_TAG:-0.1.0}"
ROUTER_SVC_TAG="${ROUTER_SVC_TAG:-0.1.1}"
AWS_REGION="${AWS_REGION:-us-east-1}"

AWS_ACCOUNT="$(aws sts get-caller-identity --query Account --output text)"
ECR_BASE="${AWS_ACCOUNT}.dkr.ecr.${AWS_REGION}.amazonaws.com"

IRSA_ARN="$(terraform -chdir="$TF_DIR" output -raw pod_manager_irsa_role_arn)"
SERVICE_NAME="$(terraform -chdir="$TF_DIR" output -raw service_name)"

helm upgrade --install "$RELEASE" "$CHART_DIR" \
  --namespace "$NAMESPACE" \
  --create-namespace \
  -f "${CHART_DIR}/values.yaml" \
  -f "${CHART_DIR}/values-aws.yaml" \
  --set "serviceAccount.roleArn=${IRSA_ARN}" \
  --set "serviceName=${SERVICE_NAME}" \
  --set "global.awsRegion=${AWS_REGION}" \
  --set "global.deployTarget=aws" \
  --set "envoy.image.repository=${ECR_BASE}/envoy-router" \
  --set "envoy.image.tag=${TAG}" \
  --set "podManager.image.repository=${ECR_BASE}/router-svc" \
  --set "podManager.image.tag=${ROUTER_SVC_TAG}" \
  --set "loginPod.image.repository=${ECR_BASE}/login-pod" \
  --set "loginPod.image.tag=${TAG}" \
  --set "backendPool.image.repository=${ECR_BASE}/backend-pool-node" \
  --set "backendPool.image.tag=${TAG}" \
  --wait --timeout 10m

echo "Helm release ${RELEASE} deployed to namespace ${NAMESPACE}"

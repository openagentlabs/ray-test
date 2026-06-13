#!/usr/bin/env bash
# Deploy routing-tier Helm release to EKS.
set -euo pipefail
set -x # Debuging

ROOT="$(dirname "${BASH_SOURCE[0]}")/../.."
TF_DIR="${ROOT}/ecs-app"
CHART_DIR="${ROOT}/ecs-app/helm/routing-tier"
NAMESPACE="${K8S_NAMESPACE:-midas-apps}"
RELEASE="${HELM_RELEASE:-routing-tier}"
TAG="${IMAGE_TAG:-latest}"
AWS_REGION="${AWS_REGION:-us-east-1}"

AWS_ACCOUNT="$(aws sts get-caller-identity --query Account --output text)"
ECR_BASE="${AWS_ACCOUNT}.dkr.ecr.${AWS_REGION}.amazonaws.com"

IRSA_ARN="$(terraform -chdir="$TF_DIR" output -raw pod_manager_irsa_role_arn)"
SERVICE_NAME="$(terraform -chdir="$TF_DIR" output -raw service_name)"

helm upgrade --install "$RELEASE" "$CHART_DIR" \
  --namespace "$NAMESPACE" \
  -f "${CHART_DIR}/values-aws.yaml" \
  --set "serviceAccount.roleArn=${IRSA_ARN}" \
  --set "serviceName=${SERVICE_NAME}" \
  --set "global.awsRegion=${AWS_REGION}" \
  --set "global.deployTarget=aws" \
  --set "envoy.image.repository=${ECR_BASE}/midas/envoy-router" \
  --set "envoy.image.tag=${TAG}" \
  --set "podManager.image.repository=${ECR_BASE}/midas/router-svc" \
  --set "podManager.image.tag=${TAG}" \
  --set "loginPool.image.repository=${ECR_BASE}/midas-dev-midas-api-backend-svc" \
  --set "loginPool.image.tag=${TAG}" \
  --set "backendPool.image.repository=${ECR_BASE}/midas-dev-midas-api-backend-svc" \
  --set "backendPool.image.tag=${TAG}" \
  --wait --timeout 10m

echo "Helm release ${RELEASE} deployed to namespace ${NAMESPACE}"

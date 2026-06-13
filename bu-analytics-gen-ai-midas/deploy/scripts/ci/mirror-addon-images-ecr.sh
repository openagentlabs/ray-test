#!/usr/bin/env bash
# Mirror third-party add-on images from public sources to the private ECR.
#
# Called from the "Push images to ECR" Jenkins stage BEFORE helm_release runs,
# so nodes can pull from private ECR (no NAT/IGW; public.ecr.aws unreachable).
#
# Idempotent — skips a tag that is already present in the target ECR repo.
# Add new entries to the MIRRORS array as more add-ons are introduced.
#
# Required env vars (set by the Jenkins stage):
#   AWS_ACCOUNT_ID   — AWS account number (e.g. 811391286931)
#   TENANT_ENV       — environment slug (e.g. dev)
#   AWS_REGION       — AWS region (default: us-east-1)
#
# Usage:
#   chmod +x deploy/scripts/ci/mirror-addon-images-ecr.sh
#   ./deploy/scripts/ci/mirror-addon-images-ecr.sh

set -euo pipefail

ACCOUNT="${AWS_ACCOUNT_ID:?AWS_ACCOUNT_ID required}"
ENV_NAME="${TENANT_ENV:?TENANT_ENV required}"
REGION="${AWS_REGION:-us-east-1}"
PRIVATE_REGISTRY="${ACCOUNT}.dkr.ecr.${REGION}.amazonaws.com"

# ---------------------------------------------------------------------------
# Add-on image mirror table
# Format: "SOURCE_IMAGE|PRIVATE_ECR_REPO_NAME|TAG"
# SOURCE_IMAGE must be the full public image reference including tag.
# PRIVATE_ECR_REPO_NAME is the repo name WITHOUT the account/region prefix.
# ---------------------------------------------------------------------------
MIRRORS=(
  "public.ecr.aws/aws-observability/aws-for-fluent-bit:2.32.2.20240516|midas-${ENV_NAME}-aws-for-fluent-bit|2.32.2.20240516"
  # CloudWatch Container Insights — agent + operator images for the
  # amazon-cloudwatch-observability Helm chart. Tags MUST match the chart's
  # bundled defaults (upstream values.yaml under agent.image.tag and
  # manager.image.tag for chart_version) AND var.agent_image_tag /
  # var.operator_image_tag in
  # deploy/ecs-app/modules/observability-cloudwatch-agent/variables.tf.
  "public.ecr.aws/cloudwatch-agent/cloudwatch-agent:1.300064.1b1344|midas-${ENV_NAME}-cloudwatch-agent|1.300064.1b1344"
  "public.ecr.aws/cloudwatch-agent/cloudwatch-agent-operator:3.3.2|midas-${ENV_NAME}-cloudwatch-agent-operator|3.3.2"
)

echo "=== ECR add-on image mirror (region=${REGION}, env=${ENV_NAME}) ==="

aws ecr get-login-password --region "$REGION" | \
  docker login --username AWS --password-stdin "$PRIVATE_REGISTRY"

for entry in "${MIRRORS[@]}"; do
  IFS='|' read -r src_image repo_name tag <<< "$entry"
  dest_image="${PRIVATE_REGISTRY}/${repo_name}:${tag}"

  # Check if the tag already exists — skip pull/push if so (idempotent).
  if aws ecr describe-images \
      --repository-name "$repo_name" \
      --image-ids imageTag="$tag" \
      --region "$REGION" \
      --output text \
      --query 'imageDetails[0].imageTags[0]' 2>/dev/null | grep -q "$tag"; then
    echo "  [SKIP] ${dest_image} already in ECR"
    continue
  fi

  echo "  [MIRROR] ${src_image} -> ${dest_image}"
  docker pull "$src_image"
  docker tag  "$src_image" "$dest_image"
  docker push "$dest_image"
  echo "  [DONE]  ${dest_image}"
done

echo "=== Add-on image mirror complete ==="

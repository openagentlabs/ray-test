#!/usr/bin/env bash
# Build and push routing-tier container images to ECR.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TF_DIR="${ROOT}/infra/terraform/environments/dev"
TAG="${IMAGE_TAG:-0.1.0}"
AWS_REGION="${AWS_REGION:-us-east-1}"

if ! command -v terraform >/dev/null 2>&1; then
  echo "terraform is required" >&2
  exit 1
fi

AWS_ACCOUNT="$(aws sts get-caller-identity --query Account --output text)"
ECR_BASE="${AWS_ACCOUNT}.dkr.ecr.${AWS_REGION}.amazonaws.com"

aws ecr get-login-password --region "$AWS_REGION" | \
  docker login --username AWS --password-stdin "${AWS_ACCOUNT}.dkr.ecr.${AWS_REGION}.amazonaws.com"

mapfile -t REPOS < <(terraform -chdir="$TF_DIR" output -json ecr_repository_urls 2>/dev/null | \
  python3 -c 'import json,sys; print("\n".join(json.load(sys.stdin).values()))' || true)

if [[ ${#REPOS[@]} -eq 0 ]]; then
  echo "ECR repos not found — run terraform apply first" >&2
  exit 1
fi

declare -A REPO_MAP=()
for url in "${REPOS[@]}"; do
  name="${url##*/}"
  REPO_MAP["$name"]="$url"
done

build_push() {
  local name="$1"
  local context="$2"
  local repo="${REPO_MAP[$name]:-}"
  if [[ -z "$repo" ]]; then
    echo "Missing ECR repo: $name" >&2
    exit 1
  fi
  echo "==> Building ${name} from ${context}"
  docker build -t "${repo}:${TAG}" "$context"
  docker push "${repo}:${TAG}"
}

build_push envoy-router "${ROOT}/envoy"
build_push router-svc "${ROOT}/router.svc"
build_push backend-pool-node "${ROOT}/pods/backend_pool_node"
build_push login-pod "${ROOT}/pods/login_pod"

echo "Pushed images with tag ${TAG}"

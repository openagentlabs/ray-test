#!/usr/bin/env bash
# Tag and push images to ECR. Requires IMAGE_TAG, AWS_ACCOUNT_ID, TENANT_ENV,
# and repository URLs from Terraform (export each URL env var before calling).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$ROOT"
MAP="deploy/ecs-app/docker/build-registry/images.yaml"
TAG="${IMAGE_TAG:?IMAGE_TAG required}"
ACCOUNT="${AWS_ACCOUNT_ID:?AWS_ACCOUNT_ID required}"
ENV_NAME="${TENANT_ENV:?TENANT_ENV required}"
REGION="${AWS_REGION:-us-east-1}"

YQ="${ROOT}/.cache-ci/yq"
mkdir -p "$(dirname "$YQ")"
if [ ! -x "$YQ" ]; then
  OS="$(uname -s | tr '[:upper:]' '[:lower:]')"
  ARCH="$(uname -m)"
  case "${OS}_${ARCH}" in
    linux_x86_64)   YQ_BINARY="yq_linux_amd64" ;;
    linux_aarch64)  YQ_BINARY="yq_linux_arm64" ;;
    darwin_x86_64)  YQ_BINARY="yq_darwin_amd64" ;;
    darwin_arm64)   YQ_BINARY="yq_darwin_arm64" ;;
    *)              echo "Unsupported platform ${OS}_${ARCH}" >&2; exit 1 ;;
  esac
  curl -fsSL "https://github.com/mikefarah/yq/releases/download/v4.44.3/${YQ_BINARY}" -o "$YQ"
  chmod +x "$YQ"
fi

aws ecr get-login-password --region "$REGION" | docker login --username AWS --password-stdin "${ACCOUNT}.dkr.ecr.${REGION}.amazonaws.com"

while IFS= read -r svc; do
  suffix=$("$YQ" e ".images[] | select(.service == \"$svc\") | .ecr_repository_suffix" "$MAP")
  # Map the suffix to its ECR_URL_* env var. Replace every non-alphanumeric
  # character (e.g. '-' and the '/' in namespaced suffixes like midas/router-svc)
  # with '_' so the result is a valid shell variable name.
  # shellcheck disable=SC2086
  url_var="ECR_URL_$(printf '%s' "$suffix" | tr -c 'A-Za-z0-9' '_')"
  repo_url="${!url_var-}"
  if [ -z "$repo_url" ]; then
    echo "ERROR: Set ${url_var} to terraform output ecr repository URL (no tag) for ${svc}" >&2
    exit 1
  fi
  echo "=== docker push: ${svc} -> ${repo_url}:${TAG} ==="
  docker tag "${svc}:${TAG}" "${repo_url}:${TAG}"
  docker push "${repo_url}:${TAG}"
done < <("$YQ" e '.images[].service' "$MAP")

echo "All images pushed."

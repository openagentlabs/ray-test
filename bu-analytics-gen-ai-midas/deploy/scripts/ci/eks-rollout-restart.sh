#!/usr/bin/env bash
# Restart MIDAS app Deployments in EKS (picks up refreshed K8s Secrets from envFrom, etc.).
# Prerequisites: aws CLI, kubectl, helm chart Chart.yaml under deploy/ecs-app/helm/<chart>/.
# Env: EKS_CLUSTER_NAME, AWS_REGION (default us-east-1). Optional IMAGE_TAG / ECR (not used here).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
REL="${ROOT}/deploy/ecs-app/helm/releases.yaml"
HELM_BASE="${ROOT}/deploy/ecs-app/helm"
CLUSTER="${EKS_CLUSTER_NAME:?EKS_CLUSTER_NAME required}"
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

NS=$("$YQ" e '.namespace' "$REL")

echo "=== Configuring kubectl for cluster: ${CLUSTER} ==="
aws eks update-kubeconfig --name "$CLUSTER" --region "$REGION"

if ! kubectl cluster-info --request-timeout=15s > /dev/null 2>&1; then
  echo "ERROR: Cannot reach EKS API for cluster '${CLUSTER}'." >&2
  exit 1
fi

count=$("$YQ" e '.releases | length' "$REL")
for i in $(seq 0 $((count - 1))); do
  chart=$("$YQ" e ".releases[$i].chart" "$REL")
  deploy_name=$("$YQ" e '.name' "${HELM_BASE}/${chart}/Chart.yaml")
  echo "=== kubectl rollout restart deployment/${deploy_name} -n ${NS} ==="
  kubectl rollout restart "deployment/${deploy_name}" -n "$NS"
done

echo "Rollout restart requested for ${count} deployment(s) in ${NS}."

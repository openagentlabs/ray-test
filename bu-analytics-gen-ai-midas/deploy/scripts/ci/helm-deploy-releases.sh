#!/usr/bin/env bash
# Run helm upgrade --install for each entry in deploy/ecs-app/helm/releases.yaml
# Requires: IMAGE_TAG, EKS_CLUSTER_NAME, ECR_URL_* env vars from Terraform outputs.
# Also syncs midas-{env}-us-east-1/app Secrets Manager secret into K8s midas-app-secret.
#
# Optional env (defaults in parentheses):
#   HELM_WAIT          - if true/1/yes, pass helm --wait and verify kubectl rollout status (true)
#   HELM_ATOMIC        - if true, also pass helm --atomic (implies wait; false)
#   HELM_TIMEOUT       - helm --timeout value (20m)
#   ROLLOUT_TIMEOUT    - kubectl rollout status --timeout (20m)
#   ROLLOUT_SUFFIX     - if set, passed as rollout.suffix on every chart (forces new ReplicaSet).
#                        Otherwise BUILD_NUMBER is used when present (Jenkins).
#   SKIP_K8S_APP_SECRET_SYNC - if true/1/yes, skip SM→K8s midas-app-secret sync (Terraform already applied it).
#   ENVIRONMENT        - environment name (default dev). Used to build the app secret name when
#                        APP_SECRET_NAME is not explicitly set.
#   APP_SECRET_NAME    - override full SM secret name (default midas-{ENVIRONMENT}-{REGION}/app).
#   BACKEND_APPLICATION_LOG_GROUP_NAME - CloudWatch Log Group for backend app logs.
#                        When set, injected as observability.logGroupName (LOG_CLOUDWATCH_LOG_GROUP)
#                        into every Helm release. Jenkins exports this from the Terraform output
#                        backend_application_log_group_name via deploy/.ci/terraform-env.sh.
#   BACKEND_REPLICA_COUNT - Override replicaCount for midas-api-backend-svc (default 3).
#                        Set to 0 when running the ec2-mt-test Job to free node capacity.
#   EC2_MT_TEST_JOB_ENABLED - When true/1/yes, the midas-ec2-mt-test-svc Job chart is deployed.
#                        When false (default), the chart is skipped (enabled=false passed to Helm).
#   EC2_MT_TEST_IRSA_ROLE_ARN - IRSA role ARN for the midas-ec2-mt-test-svc ServiceAccount.
#                        Exported from Terraform output ec2_mt_test_irsa_role_arn via
#                        deploy/.ci/terraform-env.sh. Required when EC2_MT_TEST_JOB_ENABLED=true.
set -euo pipefail

truthy() {
  case "${1:-}" in
    1|true|TRUE|yes|YES) return 0 ;;
    *) return 1 ;;
  esac
}
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
REL="${ROOT}/deploy/ecs-app/helm/releases.yaml"
HELM_BASE="${ROOT}/deploy/ecs-app/helm"
TAG="${IMAGE_TAG:?IMAGE_TAG required}"
CLUSTER="${EKS_CLUSTER_NAME:?EKS_CLUSTER_NAME required}"
REGION="${AWS_REGION:-us-east-1}"
ENVIRONMENT="${ENVIRONMENT:-dev}"
# Build default SM app secret name from environment + region so non-dev environments work
# without an explicit APP_SECRET_NAME override. Jenkins passes ENVIRONMENT from the
# customer-mapping or Jenkinsfile_Deploy_App parameters; dev is the safe fallback.
APP_SECRET_NAME="${APP_SECRET_NAME:-midas-${ENVIRONMENT}-${REGION}/app}"
K8S_SECRET_NAME="midas-app-secret"

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

# Configure kubectl - EKS API is private-only (endpoint_public_access=false).
# The Jenkins agent must be in the same VPC or connected via Transit Gateway.
# The midas-deployer-role is granted AmazonEKSClusterAdminPolicy via Terraform
# (deploy/ecs-app/modules/eks/main.tf aws_eks_access_entry.deployer).
echo "=== Configuring kubectl for cluster: ${CLUSTER} ==="
aws eks update-kubeconfig --name "$CLUSTER" --region "$REGION"

# Pre-flight: confirm we can reach the API before proceeding
if ! kubectl cluster-info --request-timeout=15s > /dev/null 2>&1; then
  echo "ERROR: Cannot reach EKS API for cluster '${CLUSTER}'." >&2
  echo "  The Jenkins agent must be in the same VPC (vpc-0c4d673f3e95a93eb) or" >&2
  echo "  connected via Transit Gateway to reach the private endpoint." >&2
  echo "  EKS private IPs: 10.72.134.171, 10.72.134.21" >&2
  exit 1
fi
echo "    kubectl connected successfully."

# ── Sync Secrets Manager → Kubernetes Secret ─────────────────────────────────
# Pulls the full JSON from midas-{ENVIRONMENT}-{REGION}/app and creates/updates the
# midas-app-secret K8s Secret in the target namespace so pods can use envFrom.
# When SKIP_K8S_APP_SECRET_SYNC is true (e.g. from Terraform output), Terraform
# already applied kubernetes_secret_v1 midas-app-secret — skip duplicate work.
if truthy "${SKIP_K8S_APP_SECRET_SYNC:-false}"; then
  echo "=== SKIP_K8S_APP_SECRET_SYNC=true — skipping SM→K8s sync for '${K8S_SECRET_NAME}' (managed by Terraform) ==="
  kubectl create namespace "$NS" --dry-run=client -o yaml | kubectl apply -f -
else
  echo "=== Syncing Secrets Manager '${APP_SECRET_NAME}' → K8s secret '${K8S_SECRET_NAME}' in ns '${NS}' ==="
  kubectl create namespace "$NS" --dry-run=client -o yaml | kubectl apply -f -

  SECRET_JSON=$(aws secretsmanager get-secret-value \
    --secret-id "$APP_SECRET_NAME" \
    --region "$REGION" \
    --query 'SecretString' \
    --output text)

  LITERAL_ARGS=()
  while IFS="=" read -r k v; do
    LITERAL_ARGS+=("--from-literal=${k}=${v}")
  done < <(python3 -c "
import json, sys, base64, re

d = json.loads(sys.stdin.read())

_B64_RE = re.compile(r'^[A-Za-z0-9+/]{20,}={0,2}$')

def _try_decode(v):
    try:
        return base64.b64decode(v + '==').decode('utf-8')
    except Exception:
        return None

# Guard: if a known ARN key landed in SM as base64(ARN) rather than a plain ARN, decode it
# before writing to K8s so pods receive the plain string via envFrom (not a base64 blob).
# This defends against double-encoding even when Terraform path is bypassed.
_ARN_KEYS = ('AWS_RDS_POSTGRES_SECRET_ID',)
for _k in _ARN_KEYS:
    _v = d.get(_k, '')
    if _v and not _v.startswith('arn:') and _B64_RE.match(_v):
        _dec = _try_decode(_v)
        if _dec and _dec.startswith('arn:'):
            sys.stderr.write('WARNING: ' + _k + ' in SM was base64-encoded; decoded to plain ARN\n')
            d[_k] = _dec

# Guard: if region keys look like base64 blobs (no hyphens, all alphanum), decode them.
_REGION_KEYS = ('AWS_REGION', 'AWS_DEFAULT_REGION', 'AWS_SECRETS_MANAGER_REGION')
_REGION_RE = re.compile(r'^[a-z]{2}-[a-z]+-[0-9]$')
for _k in _REGION_KEYS:
    _v = d.get(_k, '')
    if _v and not _REGION_RE.match(_v) and _B64_RE.match(_v):
        _dec = _try_decode(_v)
        if _dec and _REGION_RE.match(_dec):
            sys.stderr.write('WARNING: ' + _k + ' in SM was base64-encoded; decoded to plain region\n')
            d[_k] = _dec

# Guard: if SSL flag looks like a base64 blob, decode it.
_ssl = d.get('AWS_SECRETS_MANAGER_VERIFY_SSL', '')
if _ssl and _ssl not in ('true', 'false') and _B64_RE.match(_ssl):
    _dec = _try_decode(_ssl)
    if _dec and _dec in ('true', 'false'):
        sys.stderr.write('WARNING: AWS_SECRETS_MANAGER_VERIFY_SSL in SM was base64-encoded; decoded\n')
        d['AWS_SECRETS_MANAGER_VERIFY_SSL'] = _dec

# Guard: GRAPHRAG_API_KEY should be a plain string — if it looks like base64 of a
# printable string, decode it. This protects against someone accidentally base64-encoding
# the key before storing it in SM.
_gk = d.get('GRAPHRAG_API_KEY', '')
if _gk and _B64_RE.match(_gk):
    _dec = _try_decode(_gk)
    if _dec and _dec.isprintable() and not _dec.startswith('arn:'):
        sys.stderr.write('WARNING: GRAPHRAG_API_KEY in SM appears base64-encoded; decoded to plain string\n')
        d['GRAPHRAG_API_KEY'] = _dec

for k, v in d.items():
    print(f'{k}={v}')
" <<< "$SECRET_JSON")

  kubectl create secret generic "$K8S_SECRET_NAME" \
    --namespace "$NS" \
    "${LITERAL_ARGS[@]}" \
    --dry-run=client -o yaml | kubectl apply -f -

  echo "    Secret '${K8S_SECRET_NAME}' synced (${#LITERAL_ARGS[@]} keys)."
fi

HELM_WAIT_VAL="${HELM_WAIT:-true}"
HELM_ATOMIC_VAL="${HELM_ATOMIC:-false}"
HELM_TIMEOUT_VAL="${HELM_TIMEOUT:-20m}"
ROLLOUT_TIMEOUT_VAL="${ROLLOUT_TIMEOUT:-20m}"

helm_extra=()
if truthy "$HELM_WAIT_VAL"; then
  helm_extra+=(--wait --timeout="$HELM_TIMEOUT_VAL")
  if truthy "$HELM_ATOMIC_VAL"; then
    helm_extra+=(--atomic)
  fi
  echo "    Helm wait: enabled (timeout ${HELM_TIMEOUT_VAL}; atomic=$(truthy "$HELM_ATOMIC_VAL" && echo true || echo false))"
else
  echo "    Helm wait: disabled (HELM_WAIT unset or false - Jenkins will not fail on stuck rollouts)"
fi

# ── Helm releases ─────────────────────────────────────────────────────────────
# Force a new ReplicaSet when Jenkins provides BUILD_NUMBER (new pod-template hash; old ReplicaSets scale to 0).
# With IMAGE_TAG=latest, Always pull so nodes do not keep an older digest for the same tag.
helm_common_sets=()
rollout_id="${ROLLOUT_SUFFIX:-${BUILD_NUMBER:-}}"
if [ -n "$rollout_id" ]; then
  helm_common_sets+=(--set-string "rollout.suffix=${rollout_id}")
fi
if [ "$TAG" = "latest" ]; then
  helm_common_sets+=(--set-string "image.pullPolicy=Always")
fi

# Observability: inject CloudWatch log group name when the Terraform output is available.
# Jenkins exports TF outputs to deploy/.ci/terraform-env.sh including
# BACKEND_APPLICATION_LOG_GROUP_NAME. When set, pass it to every Helm release
# as observability.logGroupName so LOG_CLOUDWATCH_LOG_GROUP is wired in the pod.
if [ -n "${BACKEND_APPLICATION_LOG_GROUP_NAME:-}" ]; then
  helm_common_sets+=(--set-string "observability.logGroupName=${BACKEND_APPLICATION_LOG_GROUP_NAME}")
  echo "    Observability: logGroupName=${BACKEND_APPLICATION_LOG_GROUP_NAME}"
fi

EC2_MT_TEST_JOB_ENABLED_VAL="${EC2_MT_TEST_JOB_ENABLED:-false}"
BACKEND_REPLICA_COUNT_VAL="${BACKEND_REPLICA_COUNT:-3}"

count=$("$YQ" e '.releases | length' "$REL")
for i in $(seq 0 $((count - 1))); do
  name=$("$YQ" e ".releases[$i].name" "$REL")
  chart=$("$YQ" e ".releases[$i].chart" "$REL")
  vf=$("$YQ" e ".releases[$i].valuesFile" "$REL")

  # ── midas-ec2-mt-test-svc: conditional deploy ────────────────────────────
  if [ "$chart" = "midas-ec2-mt-test-svc" ]; then
    if ! truthy "$EC2_MT_TEST_JOB_ENABLED_VAL"; then
      echo "=== Skipping ${name}: EC2_MT_TEST_JOB_ENABLED=${EC2_MT_TEST_JOB_ENABLED_VAL} ==="
      continue
    fi
    # Derive ECR URL for the test image
    url_var="ECR_URL_$(echo "$chart" | tr '-' '_')"
    repo_url="${!url_var-}"
    if [ -z "$repo_url" ]; then
      echo "ERROR: missing env ${url_var} for chart ${chart}" >&2
      exit 1
    fi
    irsa_arn="${EC2_MT_TEST_IRSA_ROLE_ARN:-}"
    echo "=== helm upgrade: ${name} (image: ${repo_url}:${TAG}, IRSA: ${irsa_arn:-<empty>}) ==="
    helm_values_flags=(-f "${HELM_BASE}/${vf}")
    env_vf="${HELM_BASE}/${chart}/values-midas-${ENVIRONMENT}.yaml"
    if [ -f "$env_vf" ]; then
      helm_values_flags+=(-f "$env_vf")
      echo "    Layering env values: ${env_vf}"
    fi
    irsa_set=()
    if [ -n "$irsa_arn" ]; then
      irsa_set+=(--set "irsaRoleArn=${irsa_arn}")
    fi
    helm upgrade --install "$name" "${HELM_BASE}/${chart}" \
      --namespace "$NS" \
      --create-namespace \
      "${helm_values_flags[@]}" \
      --set "image.repository=${repo_url}" \
      --set "image.tag=${TAG}" \
      --set "enabled=true" \
      "${irsa_set[@]}" \
      "${helm_extra[@]}" \
      "${helm_common_sets[@]}"
    continue
  fi

  # ── Standard application service charts ──────────────────────────────────
  # ECR URL env var: ECR_URL_<chart_with_dashes_as_underscores>
  url_var="ECR_URL_$(echo "$chart" | tr '-' '_')"
  repo_url="${!url_var-}"
  if [ -z "$repo_url" ]; then
    echo "ERROR: missing env ${url_var} for chart ${chart}" >&2
    echo "  Expected one of the Terraform outputs exported as ECR_URL_* in deploy/.ci/terraform-env.sh" >&2
    exit 1
  fi
  echo "=== helm upgrade: ${name} (image: ${repo_url}:${TAG}) ==="

  # Per-chart overrides.
  # Always pass replicaCount for backend so Jenkins/runtime intent wins over chart
  # defaults and rollouts are predictable across environments.
  chart_extra_sets=()
  if [ "$chart" = "midas-api-backend-svc" ]; then
    chart_extra_sets+=(--set "replicaCount=${BACKEND_REPLICA_COUNT_VAL}")
    echo "    replicaCount override: ${BACKEND_REPLICA_COUNT_VAL}"
  fi

  # Build -f flags: base values file first, then optional per-environment overlay
  # (e.g. values-midas-dev.yaml) when it exists alongside the chart's values.yaml.
  helm_values_flags=(-f "${HELM_BASE}/${vf}")
  env_vf="${HELM_BASE}/${chart}/values-midas-${ENVIRONMENT}.yaml"
  if [ -f "$env_vf" ]; then
    helm_values_flags+=(-f "$env_vf")
    echo "    Layering env values: ${env_vf}"
  fi
  helm upgrade --install "$name" "${HELM_BASE}/${chart}" \
    --namespace "$NS" \
    --create-namespace \
    "${helm_values_flags[@]}" \
    --set "image.repository=${repo_url}" \
    --set "image.tag=${TAG}" \
    --set "appSecret.secretName=${K8S_SECRET_NAME}" \
    --set "appSecret.create=false" \
    "${helm_extra[@]}" \
    "${helm_common_sets[@]}" \
    "${chart_extra_sets[@]}"
done

echo "Helm releases applied in namespace ${NS}."

if truthy "$HELM_WAIT_VAL"; then
  echo "=== kubectl rollout status (timeout ${ROLLOUT_TIMEOUT_VAL}) ==="
  for i in $(seq 0 $((count - 1))); do
    chart=$("$YQ" e ".releases[$i].chart" "$REL")
    # midas-ec2-mt-test-svc is a Job, not a Deployment - skip rollout status.
    if [ "$chart" = "midas-ec2-mt-test-svc" ]; then
      if truthy "$EC2_MT_TEST_JOB_ENABLED_VAL"; then
        echo "    Skipping rollout status for Job chart ${chart} (not a Deployment)."
      fi
      continue
    fi
    deploy_name=$("$YQ" e '.name' "${HELM_BASE}/${chart}/Chart.yaml")
    echo "    deployment/${deploy_name}"
    kubectl rollout status "deployment/${deploy_name}" -n "$NS" --timeout="$ROLLOUT_TIMEOUT_VAL"
  done
  echo "    All deployments reported successful rollout."
fi

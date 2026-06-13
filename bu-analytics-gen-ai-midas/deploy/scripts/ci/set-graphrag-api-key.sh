#!/usr/bin/env bash
# set-graphrag-api-key.sh
# ---------------------------------------------------------------------------
# Inject (or update) GRAPHRAG_API_KEY in the MIDAS app Secrets Manager secret
# and immediately sync it into the live K8s midas-app-secret.
#
# Usage:
#   ./deploy/scripts/ci/set-graphrag-api-key.sh [ENVIRONMENT]
#
# The script reads GRAPHRAG_API_KEY from:
#   1. The environment variable GRAPHRAG_API_KEY  (highest priority)
#   2. A prompt (if running interactively and the var is not set)
#
# Key format expected by the GraphRAG service:
#   GRAPHRAG_API_KEY="<value>"   e.g. GRAPHRAG_API_KEY="Bf..."
#   Plain string only — do NOT base64-encode the value before passing it.
#   The script stores the plain string in Secrets Manager; the K8s sync also
#   writes plain strings so pods receive the value via envFrom without any
#   extra decoding (kubernetes_secret_v1 .data handles base64 internally).
#
# Required AWS permissions (assumed via the active AWS profile / role):
#   secretsmanager:GetSecretValue, secretsmanager:PutSecretValue
#   eks:DescribeCluster (for aws eks update-kubeconfig)
#   eks:AccessKubernetesApi + kubectl access via the deployer role
#
# Environment variables:
#   GRAPHRAG_API_KEY    - the API key value (plain string)
#   ENVIRONMENT         - target environment (default: dev)
#   AWS_REGION          - AWS region (default: us-east-1)
#   SKIP_K8S_SYNC       - set to true to skip the K8s secret sync step
#   EKS_CLUSTER_NAME    - override EKS cluster name (default: midas-eks-{ENVIRONMENT})
# ---------------------------------------------------------------------------
set -euo pipefail

ENVIRONMENT="${1:-${ENVIRONMENT:-dev}}"
REGION="${AWS_REGION:-us-east-1}"
SECRET_NAME="midas-${ENVIRONMENT}-${REGION}/app"
SKIP_K8S_SYNC="${SKIP_K8S_SYNC:-false}"
EKS_CLUSTER="${EKS_CLUSTER_NAME:-midas-eks-${ENVIRONMENT}}"
K8S_SECRET_NAME="midas-app-secret"
K8S_NS="midas-apps"

# ── 1. Resolve the API key ────────────────────────────────────────────────
if [ -z "${GRAPHRAG_API_KEY:-}" ]; then
  if [ -t 0 ]; then
    # Interactive: prompt (input hidden)
    echo -n "Enter GRAPHRAG_API_KEY (input hidden): "
    read -rs GRAPHRAG_API_KEY
    echo ""
  else
    echo "ERROR: GRAPHRAG_API_KEY is not set. Export it before running:" >&2
    echo "  export GRAPHRAG_API_KEY=\"<your-key>\"" >&2
    echo "  ./deploy/scripts/ci/set-graphrag-api-key.sh ${ENVIRONMENT}" >&2
    exit 1
  fi
fi

if [ -z "${GRAPHRAG_API_KEY}" ]; then
  echo "ERROR: GRAPHRAG_API_KEY must not be empty." >&2
  exit 1
fi

echo "=== Updating GRAPHRAG_API_KEY in Secrets Manager: ${SECRET_NAME} (${REGION}) ==="

# ── 2. Merge GRAPHRAG_API_KEY into the existing SM secret JSON ───────────
# Fetch current secret, merge the new key, push back. This preserves all
# other keys (RDS, region, etc.) already in the secret.
UPDATED_JSON=$(python3 - <<PYEOF
import json, subprocess, sys

secret_name = "${SECRET_NAME}"
region = "${REGION}"
new_key = "${GRAPHRAG_API_KEY}"

# Fetch existing secret
try:
    raw = subprocess.check_output(
        ["aws", "secretsmanager", "get-secret-value",
         "--secret-id", secret_name,
         "--region", region,
         "--query", "SecretString",
         "--output", "text"],
        text=True, stderr=subprocess.DEVNULL
    ).strip()
    existing = json.loads(raw) if raw else {}
    if not isinstance(existing, dict):
        existing = {}
except Exception as e:
    sys.stderr.write("WARNING: could not fetch existing secret (" + str(e) + "); starting from empty dict.\n")
    existing = {}

# Merge — GRAPHRAG_API_KEY wins
existing["GRAPHRAG_API_KEY"] = new_key
print(json.dumps(existing))
PYEOF
)

# Push merged JSON back to SM
aws secretsmanager put-secret-value \
  --secret-id "${SECRET_NAME}" \
  --secret-string "${UPDATED_JSON}" \
  --region "${REGION}"

echo "    GRAPHRAG_API_KEY written to ${SECRET_NAME}."

# ── 3. Optionally sync SM → K8s midas-app-secret ─────────────────────────
if [ "${SKIP_K8S_SYNC}" = "true" ]; then
  echo ""
  echo "=== SKIP_K8S_SYNC=true — skipping K8s sync. ==="
  echo "    Run helm-deploy-releases.sh or terraform apply to sync the secret to K8s."
else
  echo ""
  echo "=== Syncing updated secret to K8s: ${K8S_SECRET_NAME} in ns ${K8S_NS} ==="

  # Configure kubectl
  aws eks update-kubeconfig --name "${EKS_CLUSTER}" --region "${REGION}"

  # Verify cluster is reachable
  if ! kubectl cluster-info --request-timeout=15s > /dev/null 2>&1; then
    echo "ERROR: Cannot reach EKS API for cluster '${EKS_CLUSTER}'." >&2
    echo "  The K8s sync was skipped. Re-run with network access, or set SKIP_K8S_SYNC=true." >&2
    echo "  The SM secret WAS updated — helm-deploy-releases.sh will sync it on the next deploy." >&2
    exit 1
  fi

  # Build --from-literal args from SM JSON (plain strings, no base64 — kubectl handles encoding)
  SECRET_JSON=$(aws secretsmanager get-secret-value \
    --secret-id "${SECRET_NAME}" \
    --region "${REGION}" \
    --query 'SecretString' \
    --output text)

  LITERAL_ARGS=()
  while IFS="=" read -r k v; do
    LITERAL_ARGS+=("--from-literal=${k}=${v}")
  done < <(python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
for k, v in d.items():
    print(f'{k}={v}')
" <<< "${SECRET_JSON}")

  kubectl create secret generic "${K8S_SECRET_NAME}" \
    --namespace "${K8S_NS}" \
    "${LITERAL_ARGS[@]}" \
    --dry-run=client -o yaml | kubectl apply -f -

  echo "    ${K8S_SECRET_NAME} synced (${#LITERAL_ARGS[@]} keys)."

  # Restart graph-svc so it picks up the new key immediately
  echo ""
  echo "=== Restarting midas-graph-svc deployment ==="
  kubectl rollout restart deployment/midas-graph-svc -n "${K8S_NS}"
  kubectl rollout status deployment/midas-graph-svc -n "${K8S_NS}" --timeout=120s
  echo "    midas-graph-svc restarted successfully."
fi

echo ""
echo "Done. GRAPHRAG_API_KEY is set in ${SECRET_NAME}."
echo ""
echo "To verify the key is present in the pod:"
echo "  kubectl exec -n ${K8S_NS} deploy/midas-graph-svc -- printenv GRAPHRAG_API_KEY"

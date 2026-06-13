#!/usr/bin/env bash
# populate-secrets.sh - two modes:
#
# MODE 1 - PUSH (manual / local): read backend/.env and push into Secrets Manager.
#   By default (MERGE_SM_APP_SECRET unset or true), existing keys in AWS are merged
#   first and .env overwrites on key collision—so Terraform-seeded RDS keys survive.
#   Set MERGE_SM_APP_SECRET=false to replace the entire secret with .env keys only.
#   Run from your laptop when you update credentials:
#     export AWS_ACCESS_KEY_ID=... AWS_SECRET_ACCESS_KEY=... AWS_SESSION_TOKEN=...
#     ./deploy/scripts/ci/populate-secrets.sh [ENVIRONMENT]
#
# MODE 2 - SYNC only (Jenkins CI): secret already exists in Secrets Manager.
#   Pull the secret and write it into the K8s midas-app-secret.
#   Set SKIP_PUSH=true to skip the file-read/push step:
#     SKIP_PUSH=true ./deploy/scripts/ci/populate-secrets.sh [ENVIRONMENT]
#
# ENVIRONMENT defaults to "dev". Secret name: midas-{environment}-us-east-1/app
set -euo pipefail

ENVIRONMENT="${1:-dev}"
REGION="${AWS_REGION:-us-east-1}"
SECRET_NAME="midas-${ENVIRONMENT}-${REGION}/app"
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
SKIP_PUSH="${SKIP_PUSH:-false}"
MERGE_SM_APP_SECRET="${MERGE_SM_APP_SECRET:-true}"

if [ "${SKIP_PUSH}" = "true" ]; then
  echo "=== SKIP_PUSH=true - skipping file read and Secrets Manager push ==="
  echo "    Secret '${SECRET_NAME}' is assumed to already be up-to-date in Secrets Manager."
else
  # ── PUSH mode: read backend/.env and push to Secrets Manager ─────────────
  # backend/.env is gitignored - only available on a developer machine.
  # In CI, set SKIP_PUSH=true and rely on the secret already being populated.
  if [ -n "${ENV_FILE:-}" ]; then
    : # already set by caller
  elif [ -f "${ROOT}/backend/.env" ]; then
    ENV_FILE="${ROOT}/backend/.env"
  else
    echo "ERROR: backend/.env not found. Either run from a machine with backend/.env" >&2
    echo "       or set SKIP_PUSH=true to skip the push step (secret must already exist)." >&2
    exit 1
  fi

  echo "=== Building secret JSON from ${ENV_FILE} (merge existing SM: ${MERGE_SM_APP_SECRET}) ==="

  SECRET_JSON=$(python3 - "$ENV_FILE" "$SECRET_NAME" "$REGION" "$MERGE_SM_APP_SECRET" <<'PYEOF'
import json, re, subprocess
import sys

env_file, secret_name, region, merge_raw = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
merge = str(merge_raw).strip().lower() not in ("0", "false", "no", "off")

payload: dict = {}
with open(env_file) as f:
    for raw in f:
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)", line)
        if not m:
            continue
        key, val = m.group(1), m.group(2).strip()
        if len(val) >= 2 and val[0] in ('"', "'") and val[-1] == val[0]:
            val = val[1:-1]
        if val:
            payload[key] = val

payload["GRAPHRAG_SERVICE_URL"] = "http://midas-graph-svc.midas-apps.svc.cluster.local:8001"
payload["GRAPHRAG_AUTOSTART"] = "false"

existing: dict = {}
if merge:
    try:
        out = subprocess.check_output(
            [
                "aws",
                "secretsmanager",
                "get-secret-value",
                "--secret-id",
                secret_name,
                "--region",
                region,
                "--query",
                "SecretString",
                "--output",
                "text",
            ],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
        if out:
            parsed = json.loads(out)
            if isinstance(parsed, dict):
                existing = parsed
    except (subprocess.CalledProcessError, json.JSONDecodeError):
        existing = {}

merged = {**existing, **payload}

# MIDAS app secret must use literal AWS region identifiers for boto3 (not base64, not
# opaque blobs). .env merge wins on duplicate keys and can overwrite Terraform-seeded
# region keys—normalize after merge.
_AWS_REGION_KEYS = ("AWS_REGION", "AWS_DEFAULT_REGION", "AWS_SECRETS_MANAGER_REGION")
_region_re = re.compile(r"^[a-z]{2}-[a-z0-9-]+-\d+$")


def _normalize_app_secret_region_keys(d: dict, default_region: str) -> None:
    for k in _AWS_REGION_KEYS:
        v = d.get(k)
        if v is None:
            continue
        s = str(v).strip()
        if not s or not _region_re.match(s):
            d[k] = default_region


_normalize_app_secret_region_keys(merged, region)

# Guard: if AWS_RDS_POSTGRES_SECRET_ID is base64(ARN) rather than a plain ARN (e.g.
# because someone copied a base64 value into their .env), decode it back to the plain ARN.
# This mirrors the region-key normalisation above and prevents double-encoding in K8s.
import base64 as _b64
_B64_RE = re.compile(r'^[A-Za-z0-9+/]{40,}={0,2}$')
_RDS_SECRET_ID_KEY = "AWS_RDS_POSTGRES_SECRET_ID"
_rid = merged.get(_RDS_SECRET_ID_KEY, "")
if _rid and not _rid.startswith("arn:") and _B64_RE.match(_rid):
    try:
        _decoded = _b64.b64decode(_rid + "==").decode("utf-8")
        if _decoded.startswith("arn:"):
            import sys as _sys
            _sys.stderr.write(
                "WARNING: " + _RDS_SECRET_ID_KEY + " was base64-encoded in .env or SM; "
                "normalised to plain ARN before push.\n"
            )
            merged[_RDS_SECRET_ID_KEY] = _decoded
    except Exception:
        pass

print(json.dumps(merged))
PYEOF
  )

  echo ""
  echo "=== Pushing to Secrets Manager: ${SECRET_NAME} (region: ${REGION}) ==="

  if aws secretsmanager describe-secret \
        --secret-id "${SECRET_NAME}" \
        --region "${REGION}" \
        --output text \
        --query 'Name' 2>/dev/null | grep -q .; then
    echo "Secret exists - updating value..."
    aws secretsmanager put-secret-value \
      --secret-id "${SECRET_NAME}" \
      --secret-string "${SECRET_JSON}" \
      --region "${REGION}"
    echo "Secret updated: ${SECRET_NAME}"
  else
    echo "Secret not found - creating..."
    aws secretsmanager create-secret \
      --name "${SECRET_NAME}" \
      --secret-string "${SECRET_JSON}" \
      --region "${REGION}"
    echo "Secret created: ${SECRET_NAME}"
  fi

  echo ""
  echo "=== Secrets Manager push complete ==="
fi

echo ""
echo "Done."
echo "  The K8s midas-app-secret sync is handled by helm-deploy-releases.sh"
echo "  (which runs aws eks update-kubeconfig first, then syncs the secret)."
echo ""
echo "  To push secrets manually from your laptop:"
echo "    cd bu-analytics-gen-ai-midas"
echo "    ./deploy/scripts/ci/populate-secrets.sh dev"
echo ""
echo "  To deploy manually after pushing secrets:"
echo "    aws eks update-kubeconfig --name midas-eks-${ENVIRONMENT} --region ${REGION}"
echo "    cd deploy/ecs-app && . .ci/terraform-env.sh"
echo "    IMAGE_TAG=latest EKS_CLUSTER_NAME=midas-eks-dev ./deploy/scripts/ci/helm-deploy-releases.sh"
echo ""
echo "  If region keys in SM were wrong (API crash on secretsmanager.* hostname):"
echo "    ./deploy/scripts/ci/fix-sm-app-aws-region-keys.sh ${ENVIRONMENT}"
echo "    # then helm-deploy-releases.sh (or terraform apply) + kubectl rollout restart deployment/midas-api-backend-svc -n midas-apps"

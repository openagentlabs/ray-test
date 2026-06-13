#!/usr/bin/env bash
# Build a self-contained manylinux wheelhouse for EC2 (Python 3.10), package the
# ec2-mt-test app code, bundle AWS CLI v2, and sync all three to S3.
# Runs on the Jenkins cicd agent (has PyPI and internet access).
# MIDAS VPC has no direct PyPI or internet; all artifacts travel via S3.
#
# Component tag: midas:component=ec2-mt-test  (bundle_id: MIDAS_EC2_MT_TEST)
#
# Usage:
#   ./deploy/scripts/ci/build-ec2-pip-wheelhouse.sh [REQUIREMENTS_FILE] [S3_BUCKET]
#
# Defaults:
#   REQUIREMENTS_FILE = deploy/scripts/ci/requirements-ec2-wheelhouse.txt
#   S3_BUCKET         = keith-bucket-test-001
#
# Produces three S3 prefixes:
#   s3://<bucket>/pip-packages/          - manylinux cp310 wheels + requirements-ec2.txt
#   s3://<bucket>/midas-ec2-mt-test/app/ - ec2-mt-test source (run_batch.py etc.)
#   s3://<bucket>/midas-ec2-mt-test/awscli/ - awscliv2.zip offline installer
#
# Environment:
#   AWS_REGION, AWS_DEFAULT_REGION (default us-east-1)
#   WHEELHOUSE_TMP - optional absolute path for wheel download dir

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$ROOT"

REQ="${1:-deploy/scripts/ci/requirements-ec2-wheelhouse.txt}"
S3_BUCKET="${2:-keith-bucket-test-001}"
REGION="${AWS_REGION:-${AWS_DEFAULT_REGION:-us-east-1}}"

S3_WHEELS="s3://${S3_BUCKET}/pip-packages/"
S3_APP="s3://${S3_BUCKET}/midas-ec2-mt-test/app/"
S3_AWSCLI="s3://${S3_BUCKET}/midas-ec2-mt-test/awscli/"
S3_TAG="Key=midas:component,Value=ec2-mt-test"

if [[ ! -f "$REQ" ]]; then
  echo "ERROR: requirements file not found: $REQ" >&2
  exit 1
fi

WHEEL_OUT="${WHEELHOUSE_TMP:-$(mktemp -d /tmp/midas-ec2-wheelhouse.XXXXXX)}"
APP_TMP="$(mktemp -d /tmp/midas-ec2-mt-test-app.XXXXXX)"
AWSCLI_TMP="$(mktemp -d /tmp/midas-ec2-awscli.XXXXXX)"
PIP_VENV="$(mktemp -d /tmp/midas-pip-venv.XXXXXX)"

cleanup() {
  [[ -z "${WHEELHOUSE_TMP:-}" ]] && rm -rf "$WHEEL_OUT" || true
  rm -rf "$APP_TMP" "$AWSCLI_TMP" "$PIP_VENV"
}
trap cleanup EXIT

echo "[ec2-mt-test] Wheel output: $WHEEL_OUT"
echo "[ec2-mt-test] Requirements: $REQ"
echo "[ec2-mt-test] S3 bucket: $S3_BUCKET"

# Jenkins agents occasionally get truncated PyPI JSON (JSONDecodeError). Use an
# isolated venv with a current pip and retry every PyPI call before failing the
# deploy stage.
python3 -m venv "$PIP_VENV"
# shellcheck disable=SC1091
source "$PIP_VENV/bin/activate"

pip_with_retry() {
  local pip_cmd attempt max_attempts delay_s
  pip_cmd="$1"
  shift
  max_attempts="${PIP_RETRY_ATTEMPTS:-5}"
  delay_s="${PIP_RETRY_DELAY_SECONDS:-15}"
  for attempt in $(seq 1 "$max_attempts"); do
    echo "[ec2-mt-test] pip ${pip_cmd} attempt ${attempt}/${max_attempts}: $*"
    if python3 -m pip "$pip_cmd" "$@" \
      --retries 10 \
      --timeout 120 \
      --no-cache-dir; then
      return 0
    fi
    if [[ "$attempt" -lt "$max_attempts" ]]; then
      echo "[ec2-mt-test] pip ${pip_cmd} failed; retrying in ${delay_s}s..." >&2
      sleep "$delay_s"
      delay_s=$((delay_s * 2))
    fi
  done
  echo "[ec2-mt-test] ERROR: pip ${pip_cmd} failed after ${max_attempts} attempts" >&2
  return 1
}

pip_install_with_retry() {
  pip_with_retry install --upgrade "$@"
}

pip_download_with_retry() {
  pip_with_retry download "$@"
}

pip_install_with_retry pip setuptools wheel

COMMON_PIP_ARGS=(
  -d "$WHEEL_OUT"
  --python-version 310
  --platform manylinux2014_x86_64
  --platform manylinux_2_17_x86_64
  --platform manylinux_2_28_x86_64
  --implementation cp
  --abi cp310
  --only-binary=:all:
)

# ── 1. Download wheels (manylinux cp310 x86_64) ─────────────────────────────
pip_download_with_retry -r "$REQ" "${COMMON_PIP_ARGS[@]}"
pip_download_with_retry pip setuptools wheel "${COMMON_PIP_ARGS[@]}"

cp "$REQ" "$WHEEL_OUT/requirements-ec2.txt"
echo "[ec2-mt-test] Wheel count: $(find "$WHEEL_OUT" -maxdepth 1 -name '*.whl' | wc -l | tr -d ' ')"

# ── 2. Stage app code ────────────────────────────────────────────────────────
# Exclude data/, catboost_info/, .venv (matches .gitignore).
rsync -a --exclude='data/' --exclude='catboost_info/' --exclude='.venv' \
  ec2-mt-test/ "$APP_TMP/"
echo "[ec2-mt-test] App files staged: $(find "$APP_TMP" -type f | wc -l | tr -d ' ')"

# ── 3. Download AWS CLI v2 installer ────────────────────────────────────────
AWSCLI_URL="https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip"
curl -fsSL "$AWSCLI_URL" -o "$AWSCLI_TMP/awscliv2.zip"
echo "[ec2-mt-test] AWS CLI v2 zip size: $(du -sh "$AWSCLI_TMP/awscliv2.zip" | cut -f1)"

# ── 4. Upload all three prefixes with component tag ──────────────────────────
echo "[ec2-mt-test] Syncing wheelhouse to $S3_WHEELS"
aws s3 sync "$WHEEL_OUT" "$S3_WHEELS" \
  --delete --only-show-errors \
  --region "$REGION"
aws s3api put-object-tagging \
  --bucket "$S3_BUCKET" \
  --key "pip-packages/requirements-ec2.txt" \
  --tagging "TagSet=[{$S3_TAG}]" \
  --region "$REGION" 2>/dev/null || true

echo "[ec2-mt-test] Syncing app code to $S3_APP"
aws s3 sync "$APP_TMP" "$S3_APP" \
  --delete --only-show-errors \
  --region "$REGION"

echo "[ec2-mt-test] Syncing AWS CLI bundle to $S3_AWSCLI"
aws s3 sync "$AWSCLI_TMP" "$S3_AWSCLI" \
  --delete --only-show-errors \
  --region "$REGION"

# Tag the awscli zip object
aws s3api put-object-tagging \
  --bucket "$S3_BUCKET" \
  --key "midas-ec2-mt-test/awscli/awscliv2.zip" \
  --tagging "TagSet=[{$S3_TAG}]" \
  --region "$REGION" 2>/dev/null || true

echo "[ec2-mt-test] Done. All artifacts tagged midas:component=ec2-mt-test"
echo "[ec2-mt-test]   Wheels : $S3_WHEELS"
echo "[ec2-mt-test]   App    : $S3_APP"
echo "[ec2-mt-test]   AWS CLI: $S3_AWSCLI"

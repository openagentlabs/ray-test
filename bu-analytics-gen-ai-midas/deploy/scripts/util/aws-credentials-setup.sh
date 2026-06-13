#!/usr/bin/env bash
# Store or replace AWS access keys in ~/.aws/credentials for a named profile.
# Safe to re-run anytime; overwrites only that profile's keys (other profiles unchanged).
#
# Usage (from repo root):
#   ./deploy/scripts/util/aws-credentials-setup.sh [profile_name] [region]
#   ./deploy/scripts/util/aws-credentials-setup.sh --block [profile_name] [region]   # paste multi-line export block on stdin
#
# Block mode examples:
#   ./deploy/scripts/util/aws-credentials-setup.sh --block <<'EOF'
#   export AWS_ACCESS_KEY_ID="ASIA..."
#   export AWS_SECRET_ACCESS_KEY="..."
#   export AWS_SESSION_TOKEN="..."
#   EOF
#
#   # Or: paste, then Ctrl-D
#   ./deploy/scripts/util/aws-credentials-setup.sh --block
#
# Defaults: profile "default", region "us-east-1" (override with arg or AWS_REGION).

set -euo pipefail

# Accept raw values or full shell lines like: export AWS_ACCESS_KEY_ID="ASIA..."
normalize_aws_paste() {
  local s="$1"
  s="$(printf '%s' "$s" | sed -E 's/^[[:space:]]+//; s/[[:space:]]+$//')"
  s="$(printf '%s' "$s" | sed -E 's/^export[[:space:]]+//')"
  s="$(printf '%s' "$s" | sed -E 's/^AWS_ACCESS_KEY_ID[[:space:]]*=[[:space:]]*//')"
  s="$(printf '%s' "$s" | sed -E 's/^AWS_SECRET_ACCESS_KEY[[:space:]]*=[[:space:]]*//')"
  s="$(printf '%s' "$s" | sed -E 's/^AWS_SESSION_TOKEN[[:space:]]*=[[:space:]]*//')"
  s="$(printf '%s' "$s" | sed -E 's/^"//; s/"$//; s/^'"'"'//; s/'"'"'$//')"
  printf '%s' "$s"
}

# Parse stdin block containing export lines (order does not matter).
parse_export_block() {
  local block="$1"
  AWS_ACCESS_KEY_ID=""
  AWS_SECRET_ACCESS_KEY=""
  AWS_SESSION_TOKEN=""
  while IFS= read -r line || [[ -n "$line" ]]; do
    line="$(printf '%s' "$line" | sed -E 's/^[[:space:]]+//; s/[[:space:]]+$//')"
    [[ -z "$line" ]] && continue
    [[ "$line" =~ ^# ]] && continue
    if [[ "$line" =~ AWS_ACCESS_KEY_ID[[:space:]]*= ]]; then
      AWS_ACCESS_KEY_ID="$(normalize_aws_paste "$line")"
    elif [[ "$line" =~ AWS_SECRET_ACCESS_KEY[[:space:]]*= ]]; then
      AWS_SECRET_ACCESS_KEY="$(normalize_aws_paste "$line")"
    elif [[ "$line" =~ AWS_SESSION_TOKEN[[:space:]]*= ]]; then
      AWS_SESSION_TOKEN="$(normalize_aws_paste "$line")"
    fi
  done <<< "$block"
}

BLOCK_MODE=false
if [[ "${1:-}" == "--block" || "${1:-}" == "-b" ]]; then
  BLOCK_MODE=true
  shift
fi

PROFILE="${1:-default}"
REGION="${2:-${AWS_REGION:-us-east-1}}"

if ! command -v aws >/dev/null 2>&1; then
  echo "ERROR: AWS CLI is not installed or not on PATH." >&2
  echo "Install it (e.g. brew install awscli) and retry." >&2
  exit 1
fi

mkdir -p "${HOME}/.aws"

echo "Profile: ${PROFILE}"
echo "Region:  ${REGION}"
echo ""

if [[ "${BLOCK_MODE}" == true ]]; then
  if [[ -t 0 ]]; then
    echo "Paste the three export lines (Access Key ID, Secret, Session Token), then press Ctrl-D:" >&2
  fi
  BLOCK=$(cat)
  parse_export_block "$BLOCK"
else
  echo "Access Key ID (AKIA… or ASIA…). Paste the value only, or a full export AWS_ACCESS_KEY_ID=… line:"
  read -r AWS_ACCESS_KEY_ID
  AWS_ACCESS_KEY_ID="$(normalize_aws_paste "${AWS_ACCESS_KEY_ID}")"

  echo "Secret Access Key (hidden). Paste the value only, or export AWS_SECRET_ACCESS_KEY=… :"
  read -rs AWS_SECRET_ACCESS_KEY
  echo ""
  AWS_SECRET_ACCESS_KEY="$(normalize_aws_paste "${AWS_SECRET_ACCESS_KEY}")"

  echo "Session token if using temporary (ASIA…) creds; else press Enter. Same paste rules:"
  read -r AWS_SESSION_TOKEN
  AWS_SESSION_TOKEN="$(normalize_aws_paste "${AWS_SESSION_TOKEN}")"
fi

if [[ -z "${AWS_ACCESS_KEY_ID}" || -z "${AWS_SECRET_ACCESS_KEY}" ]]; then
  echo "ERROR: Access key id and secret access key are required." >&2
  exit 1
fi

if [[ "${AWS_ACCESS_KEY_ID}" == ASIA* && -z "${AWS_SESSION_TOKEN}" ]]; then
  echo "WARNING: ASIA* keys are temporary; you almost always need a session token. If AWS fails, re-run and paste the token." >&2
fi

aws configure set aws_access_key_id "${AWS_ACCESS_KEY_ID}" --profile "${PROFILE}"
aws configure set aws_secret_access_key "${AWS_SECRET_ACCESS_KEY}" --profile "${PROFILE}"
aws configure set region "${REGION}" --profile "${PROFILE}"

if [[ -n "${AWS_SESSION_TOKEN}" ]]; then
  aws configure set aws_session_token "${AWS_SESSION_TOKEN}" --profile "${PROFILE}"
fi

unset AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN

CREDS="${HOME}/.aws/credentials"
if [[ -f "${CREDS}" ]]; then
  chmod 600 "${CREDS}" || true
fi
CONFIG="${HOME}/.aws/config"
if [[ -f "${CONFIG}" ]]; then
  chmod 600 "${CONFIG}" || true
fi

echo ""
echo "Done. Credentials updated for profile '${PROFILE}'."
echo "Use this profile in your shell (and in Cursor's terminal):"
echo "  export AWS_PROFILE=${PROFILE}"
echo "  export AWS_DEFAULT_REGION=${REGION}"
echo ""
echo "Verify: aws sts get-caller-identity --profile ${PROFILE}"
echo ""
echo "If you move from temporary (STS) to long-lived keys for this profile, remove any"
echo "  aws_session_token line under [${PROFILE}] in ~/.aws/credentials if present."

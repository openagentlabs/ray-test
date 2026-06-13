#!/usr/bin/env bash
# populate-secrets.sh — populate AI Gateway "manual-input" secrets in MIDAS Secrets Manager.
#
# Why this exists:
#   The upstream ai_gateway Terraform creates 3 secrets that DO NOT have a
#   companion `aws_secretsmanager_secret_version` resource — they're meant to be
#   populated out-of-band. On a fresh MIDAS deploy (account 811391286931) the
#   secrets exist with no version, so any `data.aws_secretsmanager_secret_version`
#   that reads them fails with `couldn't find resource`, which aborts the
#   `terragrunt apply`. This script fills in safe placeholder values so the
#   pipeline can proceed. Real values must be substituted before going to UAT/PROD.
#
# Secrets handled:
#   1. ${cluster}-langfuse-ee-license              -> placeholder string until M-7 license purchase
#   2. langfuse-cognito-client-id-${cluster}       -> auto-detected from Cognito user pool client
#   3. langfuse-cognito-client-secret-${cluster}   -> auto-detected from Cognito user pool client
#
# AUTH MODEL (mirrors deploy/scripts/util/aws-credentials-setup.sh):
#   We trust the caller to be already authenticated to AWS account 811391286931.
#   Two modes are supported:
#     A) AWS_PROFILE=<profile-from-sso-login> in your shell (recommended).
#        Run `aws sso login --profile midas-dev` first.
#     B) AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY / AWS_SESSION_TOKEN exported.
#   Either way the script verifies the identity is in account 811391286931
#   before touching any secret. Aborts immediately if it isn't.
#
# Usage:
#   ./deploy/ai_gateway/scripts/populate-secrets.sh \
#       [--cluster midas-eks-aigtw-dev] \
#       [--user-pool-id <COGNITO_USER_POOL_ID>] \
#       [--ee-license-value '<real_license>']  \
#       [--dry-run] [--force]
#
# Defaults:
#   --cluster           midas-eks-aigtw-dev      (matches eks_cluster_name in terragrunt.hcl)
#   --user-pool-id      auto-discovered from `aws cognito-idp list-user-pools --max-results 60`
#   --ee-license-value  REPLACE_ME-langfuse-ee-license-key-<random>
#   --dry-run           print actions without writing
#   --force             overwrite even if a current version already exists
set -euo pipefail

# ============================================================================
# constants
# ============================================================================
EXPECTED_ACCOUNT_ID="811391286931"
DEFAULT_REGION="us-east-1"
DEFAULT_CLUSTER="midas-eks-aigtw-dev"
LANGFUSE_OBSERVABILITY_CLIENT_NAME="langfuse-observability-dev"

# ============================================================================
# arg parsing
# ============================================================================
CLUSTER="$DEFAULT_CLUSTER"
USER_POOL_ID=""
EE_LICENSE_VALUE=""
DRY_RUN=false
FORCE=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --cluster)          CLUSTER="$2"; shift 2 ;;
    --user-pool-id)     USER_POOL_ID="$2"; shift 2 ;;
    --ee-license-value) EE_LICENSE_VALUE="$2"; shift 2 ;;
    --dry-run)          DRY_RUN=true; shift ;;
    --force)            FORCE=true; shift ;;
    -h|--help)
      sed -n '2,40p' "$0" | sed 's/^# \{0,1\}//'
      exit 0 ;;
    *)
      echo "ERROR: unknown arg $1" >&2; exit 2 ;;
  esac
done

REGION="${AWS_REGION:-${AWS_DEFAULT_REGION:-$DEFAULT_REGION}}"

# ============================================================================
# helpers
# ============================================================================
say() { printf '[populate-secrets] %s\n' "$*"; }
die() { printf '[populate-secrets][ERROR] %s\n' "$*" >&2; exit 1; }

run() {
  if $DRY_RUN; then
    printf '[populate-secrets][DRY-RUN] %s\n' "$*"
  else
    eval "$@"
  fi
}

verify_aws_auth() {
  command -v aws >/dev/null 2>&1 || die "aws CLI not on PATH (brew install awscli)."

  local who
  who="$(aws sts get-caller-identity --output json 2>&1)" || \
    die "aws sts get-caller-identity failed. If using SSO run \`aws sso login --profile <name>\` first. Output:\n$who"
  local actual_account
  actual_account="$(printf '%s' "$who" | python3 -c "import json,sys; print(json.load(sys.stdin)['Account'])")"

  if [[ "$actual_account" != "$EXPECTED_ACCOUNT_ID" ]]; then
    die "Auth is for account $actual_account, expected $EXPECTED_ACCOUNT_ID (ns-ai-midas-dev-use1-dev). Refusing to touch secrets."
  fi

  local arn
  arn="$(printf '%s' "$who" | python3 -c "import json,sys; print(json.load(sys.stdin)['Arn'])")"
  say "AWS auth OK: account=$actual_account arn=$arn"
  say "Region: $REGION"
}

discover_user_pool_id() {
  if [[ -n "$USER_POOL_ID" ]]; then
    say "Using --user-pool-id $USER_POOL_ID"
    return
  fi
  # Try the var.cognito_upn-style names that this MIDAS overlay uses, in priority order:
  #   1) midas-aigtw-${env}-user-pool   (matches deploy/ai_gateway/terraform/environment/${env}/terragrunt.hcl)
  #   2) ${CLUSTER}-user-pool           (legacy upstream pattern)
  local env_short="${CLUSTER##midas-eks-aigtw-}"
  local candidates=("midas-aigtw-${env_short}-user-pool" "${CLUSTER}-user-pool")
  local pools
  pools="$(aws cognito-idp list-user-pools --max-results 60 --region "$REGION" --output json)"
  for cand in "${candidates[@]}"; do
    USER_POOL_ID="$(printf '%s' "$pools" | python3 -c "
import json, sys
data = json.load(sys.stdin)
target = sys.argv[1]
for p in data.get('UserPools', []):
    if p['Name'] == target:
        print(p['Id']); break
" "$cand")"
    if [[ -n "$USER_POOL_ID" ]]; then
      say "Discovered Cognito user pool: $USER_POOL_ID (name=$cand)"
      return
    fi
  done
  say "WARNING: no Cognito user pool found matching ${candidates[*]}."
  say "         Cognito clients haven't been created yet — will populate the EE license placeholder only."
}

# Returns the client_id (and exports CLIENT_SECRET) for the langfuse-observability client.
discover_langfuse_observability_client() {
  if [[ -z "$USER_POOL_ID" ]]; then
    LANGFUSE_CLIENT_ID=""
    LANGFUSE_CLIENT_SECRET=""
    return
  fi
  local clients
  clients="$(aws cognito-idp list-user-pool-clients --user-pool-id "$USER_POOL_ID" --max-results 60 --region "$REGION" --output json)"
  LANGFUSE_CLIENT_ID="$(printf '%s' "$clients" | python3 -c "
import json, sys
data = json.load(sys.stdin)
target = sys.argv[1]
for c in data.get('UserPoolClients', []):
    if c['ClientName'] == target:
        print(c['ClientId']); break
" "$LANGFUSE_OBSERVABILITY_CLIENT_NAME")"
  if [[ -z "$LANGFUSE_CLIENT_ID" ]]; then
    say "WARNING: no Cognito client named '$LANGFUSE_OBSERVABILITY_CLIENT_NAME' in user pool $USER_POOL_ID."
    LANGFUSE_CLIENT_SECRET=""
    return
  fi
  LANGFUSE_CLIENT_SECRET="$(aws cognito-idp describe-user-pool-client --user-pool-id "$USER_POOL_ID" --client-id "$LANGFUSE_CLIENT_ID" --region "$REGION" --query 'UserPoolClient.ClientSecret' --output text)"
  say "Discovered langfuse client: id=$LANGFUSE_CLIENT_ID secret=<${#LANGFUSE_CLIENT_SECRET} chars>"
}

# Check current version of a secret. Returns 0 if a current version exists.
secret_has_current_version() {
  local secret_id="$1"
  aws secretsmanager get-secret-value --secret-id "$secret_id" --region "$REGION" --output text --query SecretString >/dev/null 2>&1
}

# Put a value into a secret (create version) iff missing or --force.
# An empty value IS valid here (it's the no-license / OSS-mode signal for Langfuse + LiteLLM)
# — we deliberately do NOT skip empty strings.
put_secret_value() {
  local secret_id="$1" value="$2" label="$3" allow_empty="${4:-no}"
  if [[ -z "$value" && "$allow_empty" != "yes" ]]; then
    say "SKIP   $label: no value to put (and allow_empty=no)."
    return
  fi
  if secret_has_current_version "$secret_id"; then
    if $FORCE; then
      say "FORCE  $label: overwriting existing current version."
    else
      say "SKIP   $label: current version already exists (re-run with --force to overwrite)."
      return
    fi
  fi
  # Empty string is rendered as '' in shell — that's a valid SecretString value.
  run "aws secretsmanager put-secret-value --secret-id '$secret_id' --region '$REGION' --secret-string '$value' >/dev/null"
  say "WROTE  $label -> $secret_id ($([[ -z "$value" ]] && echo '<empty string — OSS mode>' || echo "${#value} chars"))"
}

# ============================================================================
# main
# ============================================================================
say "Cluster: $CLUSTER"
verify_aws_auth
discover_user_pool_id
discover_langfuse_observability_client

# 1) langfuse EE license
# DESIGN: default to EMPTY STRING. Per langfuse.com/self-hosting/license-key, omitting the
# LANGFUSE_EE_LICENSE_KEY env var (or setting it to "") triggers OSS mode — the MIT-licensed
# build with all CORE features and no scaling limits. Setting it to ANY non-empty placeholder
# makes Langfuse run license validation, which fails and crashes the pod on startup.
# When MIDAS purchases a real EE license (SOP M-7), pass --ee-license-value '<real>' to override.
EE_SECRET_ID="${CLUSTER}-langfuse-ee-license"
if [[ -z "$EE_LICENSE_VALUE" ]]; then
  say "NOTE   No --ee-license-value provided; writing EMPTY string (= OSS mode, no license)."
  say "       Pass --ee-license-value '<key>' once SOP M-7 (license purchase) is complete."
fi
put_secret_value "$EE_SECRET_ID" "$EE_LICENSE_VALUE" "langfuse-ee-license" "yes"

# 2) langfuse cognito client id
CLIENT_ID_SECRET_ID="langfuse-cognito-client-id-${CLUSTER}"
put_secret_value "$CLIENT_ID_SECRET_ID" "${LANGFUSE_CLIENT_ID:-}" "langfuse-cognito-client-id"

# 3) langfuse cognito client secret
CLIENT_SECRET_SECRET_ID="langfuse-cognito-client-secret-${CLUSTER}"
put_secret_value "$CLIENT_SECRET_SECRET_ID" "${LANGFUSE_CLIENT_SECRET:-}" "langfuse-cognito-client-secret"

say "Done."

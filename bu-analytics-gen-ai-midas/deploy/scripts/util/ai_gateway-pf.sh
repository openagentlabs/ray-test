#!/usr/bin/env bash
# ai_gateway (Exlerate) only — no MIDAS tunnels. Requires LITELLM_*, LANGFUSE_*, C1_ALB_HOST (see .py --help).
# Also passes --region, --target (jumpbox), --ai-eks-cluster (overridable via AWS_REGION, JUMPBOX_ID, AI_EKS_CLUSTER).
# For NLB/ALB-only (no Exlerate pod autoresolve), append: --no-litellm-pod --no-langfuse-pod --no-c1-pod
# One-line copy-paste: see top comment in aws-ssm-port-forward-midas-and-ai-gateway.py
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
TPROF="${AWS_PROFILE:-midas-dev}"
TREGION="${AWS_REGION:-us-east-1}"
JUMP="${JUMPBOX_ID:-i-04231b2a8a4d98b63}"
AIKUBE="${AI_EKS_CLUSTER:-exlerate-dev}"
exec python3 "$REPO_ROOT/deploy/scripts/util/aws-ssm-port-forward-midas-and-ai-gateway.py" \
  --profile "$TPROF" \
  --region "$TREGION" \
  --target "$JUMP" \
  --ai-gateway-only \
  --ai-eks-cluster "$AIKUBE" \
  --litellm-nlb-host "${LITELLM_NLB_HOST:?set LITELLM_NLB_HOST}" \
  --litellm-alb-host "${LITELLM_ALB_HOST:?set LITELLM_ALB_HOST}" \
  --langfuse-nlb-host "${LANGFUSE_NLB_HOST:?set LANGFUSE_NLB_HOST}" \
  --langfuse-alb-host "${LANGFUSE_ALB_HOST:?set LANGFUSE_ALB_HOST}" \
  --c1-alb-host "${C1_ALB_HOST:?set C1_ALB_HOST}" \
  "$@"

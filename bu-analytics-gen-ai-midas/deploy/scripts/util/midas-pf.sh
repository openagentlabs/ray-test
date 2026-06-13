#!/usr/bin/env bash
# Fetches MIDAS NLB/ALB DNS from deploy/ecs-app Terraform outputs and runs the
# SSM port-forward script. Requires: terraform in PATH, valid state in deploy/ecs-app
# (init already done), AWS creds, Session Manager plugin.
# Extra args are passed to the Python script, e.g.  --with-ai-gateway --litellm-nlb-host ...
#
# Single-line from repository root — Terraform must use the same profile as the script
# (``terraform`` does not read ``--profile``; set ``AWS_PROFILE`` for the subshell):
#   python3 deploy/scripts/util/aws-ssm-port-forward-midas-and-ai-gateway.py --profile midas-dev --midas-nlb-host "$(AWS_PROFILE=midas-dev terraform -chdir=deploy/ecs-app output -raw nlb_dns_name)" --midas-alb-host "$(AWS_PROFILE=midas-dev terraform -chdir=deploy/ecs-app output -raw alb_dns_name)"
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
TFEC="$REPO_ROOT/deploy/ecs-app"
TPROF="${AWS_PROFILE:-midas-dev}"
MNLB="$(AWS_PROFILE="$TPROF" terraform -chdir="$TFEC" output -raw nlb_dns_name)"
MALB="$(AWS_PROFILE="$TPROF" terraform -chdir="$TFEC" output -raw alb_dns_name)"
exec python3 "$REPO_ROOT/deploy/scripts/util/aws-ssm-port-forward-midas-and-ai-gateway.py" \
  --profile "$TPROF" \
  --midas-nlb-host "$MNLB" \
  --midas-alb-host "$MALB" \
  "$@"

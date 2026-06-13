#!/usr/bin/env bash
# Run on the SSM jumpbox in the Midas VPC to prove HTTPS FQDN -> NLB -> ALB -> frontend
# (same path corporate must use: private IP of NLB, SNI+Host = public FQDN).
#
# Usage (from laptop with SSM, after aws sso login and profile to account 811391286931):
#   aws ssm start-session --target i-04231b2a8a4d98b63 --region us-east-1
#   bash verify-midas-fqdn-in-vpc.sh
#
# Or: pipe this file through SSM send-command (see repo history) as base64 | bash.

set -euo pipefail

NLB_DNS="${NLB_DNS:-midas-dev-nlb-d290764c37bb4f68.elb.us-east-1.amazonaws.com}"
ALB_DNS="${ALB_DNS:-internal-midas-dev-alb-2046892741.us-east-1.elb.amazonaws.com}"
FQDN="${FQDN:-exldecision-ai-dev.exlservice.com}"

echo "=== NLB A (private) ==="
dig +short "$NLB_DNS" A
NIP=$(dig +short "$NLB_DNS" A | head -1)
if [[ -z "$NIP" ]]; then
  echo "error: no NLB IP" >&2
  exit 1
fi
echo "Using NLB IP for --resolve: $NIP"
echo
echo "=== FQDN over NLB (SNI exldecision) — expect 200 and HTML if stack OK ==="
curl -skI "https://${FQDN}/" --resolve "${FQDN}:443:${NIP}" --connect-timeout 15 | head -15
echo
echo "Body sample:"
curl -sk "https://${FQDN}/" --resolve "${FQDN}:443:${NIP}" --connect-timeout 15 | head -c 200
echo
echo
echo "=== (optional) direct ALB with Host: FQDN ==="
curl -skI "https://${ALB_DNS}/" -H "Host: ${FQDN}" --connect-timeout 15 | head -10

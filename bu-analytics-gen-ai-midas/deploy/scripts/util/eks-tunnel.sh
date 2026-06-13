#!/usr/bin/env bash
# eks-tunnel.sh - SSM port-forward tunnel to the private EKS API server.
#
# Usage:
#   1. Export your AWS credentials first:
#        export AWS_ACCESS_KEY_ID=...
#        export AWS_SECRET_ACCESS_KEY=...
#        export AWS_SESSION_TOKEN=...
#        export AWS_DEFAULT_REGION=us-east-1
#
#   2. Run this script in a separate terminal (it stays in the foreground):
#        ./deploy/scripts/eks-tunnel.sh
#
#   3. In another terminal, use kubectl normally:
#        kubectl get nodes
#        kubectl get pods -A
#
# How it works:
#   - Forwards local port 8443 → EKS API private IP 10.72.134.171:443
#     through the SSM jump host (i-0654dcf92a08a6dca / midas-dev-ec2-ssm-test).
#   - Patches ~/.kube/config to point the midas-eks-dev cluster server to
#     https://127.0.0.1:8443 and disables TLS server name verification
#     (the cert is issued for the real hostname, not 127.0.0.1).
#   - On exit (Ctrl-C), restores the original server URL in kubeconfig.

set -euo pipefail

JUMP_INSTANCE="i-0654dcf92a08a6dca"
EKS_PRIVATE_IP="10.72.134.171"
EKS_API_PORT="443"
LOCAL_PORT="8443"
REGION="${AWS_DEFAULT_REGION:-us-east-1}"
CLUSTER_NAME="midas-eks-dev"
KUBECONFIG_PATH="$HOME/.kube/config"

ORIGINAL_SERVER="https://D215BDB7961B3419B289036FAEC57DC8.gr7.us-east-1.eks.amazonaws.com"
TUNNEL_SERVER="https://127.0.0.1:${LOCAL_PORT}"

# Ensure kubeconfig exists for this cluster
aws eks update-kubeconfig --name "$CLUSTER_NAME" --region "$REGION" 2>/dev/null || true

echo "==> Patching kubeconfig: server → ${TUNNEL_SERVER}"
# Replace the server URL and add insecure-skip-tls-verify
python3 - <<PYEOF
import yaml, sys

path = "$KUBECONFIG_PATH"
with open(path) as f:
    cfg = yaml.safe_load(f)

for cluster in cfg.get('clusters', []):
    if cluster['name'] == 'arn:aws:eks:${REGION}:811391286931:cluster/${CLUSTER_NAME}':
        cluster['cluster']['server'] = '${TUNNEL_SERVER}'
        cluster['cluster']['insecure-skip-tls-verify'] = True
        cluster['cluster'].pop('certificate-authority-data', None)
        print(f"  Patched cluster: {cluster['name']}")

with open(path, 'w') as f:
    yaml.dump(cfg, f, default_flow_style=False)
PYEOF

cleanup() {
    echo ""
    echo "==> Restoring kubeconfig: server → ${ORIGINAL_SERVER}"
    python3 - <<PYEOF
import yaml
path = "$KUBECONFIG_PATH"
with open(path) as f:
    cfg = yaml.safe_load(f)
for cluster in cfg.get('clusters', []):
    if cluster['name'] == 'arn:aws:eks:${REGION}:811391286931:cluster/${CLUSTER_NAME}':
        cluster['cluster']['server'] = '${ORIGINAL_SERVER}'
        cluster['cluster'].pop('insecure-skip-tls-verify', None)
with open(path, 'w') as f:
    yaml.dump(cfg, f, default_flow_style=False)
print("  Restored.")
PYEOF
    exit 0
}
trap cleanup INT TERM

echo "==> Starting SSM tunnel: localhost:${LOCAL_PORT} → ${EKS_PRIVATE_IP}:${EKS_API_PORT}"
echo "    Jump host: ${JUMP_INSTANCE} (midas-dev-ec2-ssm-test)"
echo "    Press Ctrl-C to stop the tunnel and restore kubeconfig."
echo ""

aws ssm start-session \
    --target "$JUMP_INSTANCE" \
    --document-name "AWS-StartPortForwardingSessionToRemoteHost" \
    --parameters "{\"host\":[\"${EKS_PRIVATE_IP}\"],\"portNumber\":[\"${EKS_API_PORT}\"],\"localPortNumber\":[\"${LOCAL_PORT}\"]}" \
    --region "$REGION"

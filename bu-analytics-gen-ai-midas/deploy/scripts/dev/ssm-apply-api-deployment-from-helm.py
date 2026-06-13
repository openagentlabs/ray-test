#!/usr/bin/env python3
"""
Build midas-api-backend-svc Deployment YAML from local Helm chart, add Helm ownership
metadata, and output AWS SSM RunShellScript parameters JSON for the jump box.

Usage (from repo root):
  python3 deploy/scripts/dev/ssm-apply-api-deployment-from-helm.py > /tmp/ssm_params.json
  aws ssm send-command --instance-ids i-... --document-name AWS-RunShellScript \\
    --parameters file:///tmp/ssm_params.json --region us-east-1

Remote: kubectl replace --force + rollout status + verify (no Helm on jump box).
"""
from __future__ import annotations

import base64
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CHART = ROOT / "deploy/ecs-app/helm/midas-api-backend-svc"
VALUES = CHART / "values.yaml"
REGION = "us-east-1"
CLUSTER = "midas-eks-dev"
NS = "midas-apps"
RELEASE = "midas-api-backend"
IMAGE_REPO = "811391286931.dkr.ecr.us-east-1.amazonaws.com/midas-dev-midas-api-backend-svc"
IMAGE_TAG = "latest"


def main() -> int:
    import time

    rollout = f"agent-{int(time.time())}"
    helm_cmd = [
        "helm",
        "template",
        "midas-api",
        str(CHART),
        "--namespace",
        NS,
        "-f",
        str(VALUES),
        "--set",
        f"image.repository={IMAGE_REPO}",
        "--set",
        f"image.tag={IMAGE_TAG}",
        "--set-string",
        f"rollout.suffix={rollout}",
        "--set",
        "appSecret.secretName=midas-app-secret",
        "--set",
        "appSecret.create=false",
        "--set-string",
        "image.pullPolicy=Always",
        "-s",
        "templates/deployment.yaml",
    ]
    raw = subprocess.check_output(helm_cmd, cwd=str(ROOT), text=True)
    try:
        import yaml  # type: ignore
    except ImportError:
        print("ERROR: pip install pyyaml", file=sys.stderr)
        return 1
    docs = list(yaml.safe_load_all(raw))
    d = docs[0]
    d.setdefault("metadata", {})
    d["metadata"].setdefault("labels", {})
    d["metadata"]["labels"]["app.kubernetes.io/managed-by"] = "Helm"
    d["metadata"].setdefault("annotations", {})
    d["metadata"]["annotations"]["meta.helm.sh/release-name"] = RELEASE
    d["metadata"]["annotations"]["meta.helm.sh/release-namespace"] = NS
    yaml_out = yaml.dump(d, default_flow_style=False, sort_keys=False)
    b64_local = base64.b64encode(yaml_out.encode()).decode()
    if "'" in b64_local:
        print("ERROR: unexpected quote in base64", file=sys.stderr)
        return 1

    remote = r"""#!/bin/bash
set -euxo pipefail
export AWS_DEFAULT_REGION=""" + REGION + r"""
KCFG=$(mktemp)
export KUBECONFIG="$KCFG"
trap 'rm -f "$KCFG"' EXIT
aws eks update-kubeconfig --name """ + CLUSTER + r""" --region "$AWS_DEFAULT_REGION" --kubeconfig "$KUBECONFIG"
MAN_B64='""" + b64_local + r"""'
echo "$MAN_B64" | base64 -d | kubectl replace -f - -n """ + NS + r""" --force
kubectl rollout status deployment/midas-api-backend-svc -n """ + NS + r""" --timeout=300s
echo "========== verify =========="
kubectl get deploy midas-api-backend-svc -n """ + NS + r""" -o json | python3 -c "import sys,json; c=json.load(sys.stdin)['spec']['template']['spec']['containers'][0]; print('ports', c.get('ports')); print('envFrom', c.get('envFrom')); print('env', [e.get('name') for e in (c.get('env') or [])])"
POD=$(kubectl get pods -n """ + NS + r""" -l app.kubernetes.io/name=midas-api-backend-svc -o json | python3 -c "import sys,json; print(json.load(sys.stdin)['items'][0]['metadata']['name'])")
kubectl exec -n """ + NS + r""" "$POD" -- printenv WEB_CONCURRENCY AWS_RDS_POSTGRES_DB_NAME || true
kubectl exec -n """ + NS + r""" "$POD" -- sh -c 'test -n "${DATABASE_URL:-}" && echo DATABASE_URL=set || echo DATABASE_URL=unset' || true
# Verify RDS connection env vars required by the secrets loader after rotation.
echo "--- RDS env check (host/port/secret-id) ---"
kubectl exec -n """ + NS + r""" "$POD" -- sh -c '
  missing=""
  for v in AWS_RDS_POSTGRES_SECRET_ID AWS_RDS_POSTGRES_HOST AWS_RDS_POSTGRES_PORT; do
    val=$(printenv "$v" 2>/dev/null || true)
    if [ -z "$val" ]; then
      echo "WARN: $v is not set in pod env"
      missing="$missing $v"
    else
      echo "OK:   $v=${val}"
    fi
  done
  if [ -n "${AWS_RDS_POSTGRES_SECRET_JSON:-}" ]; then
    echo "INFO: AWS_RDS_POSTGRES_SECRET_JSON is set (inline bypass active - no GetSecretValue call)"
  fi
  if [ -n "$missing" ]; then
    echo "ERROR: missing required RDS env vars:$missing"
    exit 1
  fi
' || true
"""
    print(json.dumps({"commands": [remote]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

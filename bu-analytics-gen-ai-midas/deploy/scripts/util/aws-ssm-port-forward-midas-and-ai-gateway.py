#!/usr/bin/env python3
"""Start one or more AWS SSM port-forwarding sessions to MIDAS and AI Gateway (Exlerate) via a jumpbox.

Uses the AWS-StartPortForwardingSessionToRemoteHost SSM document to tunnel traffic
from local ports → SSM agent on the jumpbox → service endpoints inside the VPC.

**MIDAS** (deploy/ecs-app/alb-nlb.tf — cluster default ``midas-eks-dev``):

    Corporate / Jumpbox → NLB TCP:443 → ALB HTTPS:443 (TLS terminates)
                                      → frontend pods HTTP:8080
                                      → backend  pods HTTP:8000
                                      → graph    pods HTTP:8001

**AI Gateway** (ai_gateway/infra/terraform/modules/alb.tf and helm/ — Exlerate EKS
default ``exlerate-dev`` in dev terragrunt):

* LiteLLM — NLB ``<eks>-nlb-litellm`` TCP:443 → ALB (ingress stack tag ``litellm``) HTTPS:443
  → service HTTP:4000. Pod-direct tunnel hits container port 4000.
* Langfuse — NLB ``<eks>-nlb-langfuse`` TCP:443 → ALB (stack ``langfuse``) HTTPS:443
  → web HTTP:3000. Pod-direct tunnel hits container port 3000.
* Control API (C1) — only ALB (ingress group ``control-api``), HTTPS:443 → HTTP:9001. There is
  no NLB target group for C1 in the AI Gateway Terraform module, so C1 is exposed
  with pod-direct + ``--c1-alb-host`` (no ``--c1-nlb``).

Tunnels for both stacks are independent. **At least one tunnel must be enabled** after
all ``--no-*`` flags: if you disable every MIDAS tunnel, pass ``--with-ai-gateway`` and
enable the Exlerate features you need (or you will get an error before any forwarding starts).

**Default localhost → remote mapping**

MIDAS (always available; ``--no-*`` to turn off):
  9081→pod:8000 backend,  9000→8080 frontend,  9083→8001 graph,  9082→**MIDAS NLB:443**,  9084→**MIDAS ALB:443**

Exlerate / AI Gateway (only with ``--with-ai-gateway``; all remote ALB/NLB listeners are 443
unless you pass ``--*-port``):
  9190→LiteLLM pod:4000,  9191→**LiteLLM NLB:443** (forwards to LiteLLM ALB),  9192→**LiteLLM ALB:443**
  9200→Langfuse pod:3000,  9201→**Langfuse NLB:443**,  9202→**Langfuse ALB:443**
  9210→C1 pod:9001,  9211→**C1 ALB:443**  (C1 has no NLB in ``ai_gateway`` Terraform)

When ``--with-ai-gateway`` is set, the run summary prints a short **local URL** reference for
Exlerate; with MIDAS-only runs that block is omitted.

In the VPC, the **Exlerate** NLB hostnames are typically
``<eks>-nlb-litellm....`` and ``<eks>-nlb-langfuse....``; ALB DNS comes from the AWS console /
``kubectl get ingress -A`` (ingress group names ``litellm``, ``langfuse``, ``control-api``).
Pass those DNS names as ``--litellm-nlb-host``, etc.

By default, when a tunnel is not disabled, that tunnel is started. Use ``--no-<name>`` to
disable (see ``--help``).

For pod IP autoresolution the script may refresh kubeconfig on the jumpbox for **two**
EKS clusters (MIDAS then Exlerate). Disable AI pod tunnels or pass host IPs to avoid the
second cluster update.

All tunnels are torn down together when you press Ctrl+C (or the process receives SIGTERM).
Shutdown sends SIGTERM/SIGKILL to the **whole POSIX process group** of each ``aws ssm
start-session`` child (not just the ``aws`` PID), so ``session-manager-plugin`` cannot
outlive the parent and leave ports forwarding in the background.

AWS profile selection:
  Every run (unless --profile is supplied) prompts you interactively:
    1) midas-dev          – use the midas-dev SSO profile
    2) default            – AWS default credential chain (no --profile flag)
    3) Enter your own     – type any profile name

  Skip the prompt by passing --profile explicitly:
    --profile midas-dev   always use midas-dev (no prompt)
    --profile default     always use the default chain (no prompt)
    --profile my-profile  always use my-profile (no prompt)

  In non-interactive / CI environments (piped stdin) the prompt is skipped and
  $AWS_PROFILE / $AWS_DEFAULT_PROFILE are used as the fallback.

Prerequisites:
  • AWS CLI v2 on PATH with valid credentials (AWS_ACCESS_KEY_ID / session token or profile)
  • AWS Systems Manager Session Manager plugin:
      https://docs.aws.amazon.com/systems-manager/latest/userguide/session-manager-working-with-install-plugin.html
  • The jumpbox EC2 instance must have the SSM agent running and an instance profile
    that allows ssm:StartSession and ssm:SendCommand.
  • kubectl does NOT need to be installed locally. Pod IP auto-resolution runs
    kubectl on the jumpbox via SSM (AWS-RunShellScript), so it works from any
    laptop without VPN or direct VPC access.
  • **Terraform** (for ``terraform output -raw nlb_dns_name`` / ``alb_dns_name``) uses
    the same credential **environment** as your shell, not the script's ``--profile``.
    In the one-liner, prefix Terraform with ``AWS_PROFILE=midas-dev`` to match
    ``--profile midas-dev`` (or run ``aws sso login --profile midas-dev`` first). If
    you still see ``InvalidClientTokenId``, your shell may export stale
    ``AWS_ACCESS_KEY_ID``/``AWS_SECRET_ACCESS_KEY`` (e.g. Conda) — run
    ``unset AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN`` in that
    session or use a subshell: ``( unset … ; AWS_PROFILE=midas-dev terraform … )``.

Service defaults (MIDAS, namespace ``midas-apps``)
  backend   host: EKS ``midas-eks-dev`` pod (label app.kubernetes.io/name=midas-api-backend-svc)
            or BACKEND_NODE_IP env var                             remote: 8000  local: 9081
  frontend  host: EKS pod (label app.kubernetes.io/name=midas-web-frontend-svc)
            or FRONTEND_NODE_IP env var                            remote: 8080  local: 9000
  graph     host: EKS pod (label app.kubernetes.io/name=midas-graph-svc)
            or GRAPH_NODE_IP env var                               remote: 8001  local: 9083
  midas nlb  host: MIDAS_NLB_HOST (or legacy NLB_DNS) (TCP 443)       remote: 443  local: 9082
  midas alb  host: MIDAS_ALB_HOST (or ALB_DNS) (HTTPS 443)             remote: 443  local: 9084
  CLI: --midas-nlb-host / --midas-alb-host  (aliases: --nlb-host, --alb-host)

Service defaults (AI Gateway, second cluster default ``exlerate-dev`` — override with --ai-eks-cluster)
  litellm_pod  namespace ``litellm``  (label override: --litellm-pod-label)  remote: 4000  local: 9190
  litellm_nlb  LITELLM_NLB_HOST                                        remote: 443   local: 9191
  litellm_alb  LITELLM_ALB_HOST                                       remote: 443   local: 9192
  langfuse_pod namespace ``langfuse`` (label override: --langfuse-pod-label) remote: 3000  local: 9200
  langfuse_nlb LANGFUSE_NLB_HOST                                    remote: 443   local: 9201
  langfuse_alb LANGFUSE_ALB_HOST                                    remote: 443   local: 9202
  c1_pod       namespace ``c1-api``    (label override: --c1-pod-label)  remote: 9001  local: 9210
  c1_alb       C1_ALB_HOST  (C1 has no NLB in Terraform)             remote: 443   local: 9211

Pod IP resolution (backend / frontend / graph – only when tunnel is enabled):
  When --<service>-host is not supplied and <SERVICE>_NODE_IP is not set, the script
  sends an AWS-RunShellScript SSM command to the jumpbox that runs:
    kubectl get pods -n <namespace> -l app.kubernetes.io/name=midas-<service>-svc \\
        -o jsonpath=...
  on the jumpbox (which has VPC access to the private EKS API server), then parses
  the podIP from the result.  This works from any laptop without VPN.
  Use --no-kubectl to skip auto-resolution and supply --<service>-host manually.

Usage examples:

  # One line from repo root: use the **same** profile for Terraform and for the script
  #    (``terraform`` ignores ``--profile``; without ``AWS_PROFILE=...`` you may get STS 403):
  python3 deploy/scripts/util/aws-ssm-port-forward-midas-and-ai-gateway.py --profile midas-dev --midas-nlb-host "$(AWS_PROFILE=midas-dev terraform -chdir=deploy/ecs-app output -raw nlb_dns_name)" --midas-alb-host "$(AWS_PROFILE=midas-dev terraform -chdir=deploy/ecs-app output -raw alb_dns_name)"
  # Equivalent wrapper:
  bash deploy/scripts/util/midas-pf.sh
  # Or set env and run the Python entrypoint only:
  python3 deploy/scripts/util/aws-ssm-port-forward-midas-and-ai-gateway.py --profile midas-dev --midas-nlb-host "$NLB_DNS" --midas-alb-host "$ALB_DNS"
  # One line, **ai_gateway only** (no MIDAS; set the five env vars; NLB/ALB only use ``--no-*-pod`` as below):
  python3 deploy/scripts/util/aws-ssm-port-forward-midas-and-ai-gateway.py --profile midas-dev --region us-east-1 --target i-04231b2a8a4d98b63 --ai-gateway-only --ai-eks-cluster exlerate-dev --litellm-nlb-host "$LITELLM_NLB_HOST" --litellm-alb-host "$LITELLM_ALB_HOST" --langfuse-nlb-host "$LANGFUSE_NLB_HOST" --langfuse-alb-host "$LANGFUSE_ALB_HOST" --c1-alb-host "$C1_ALB_HOST" --no-litellm-pod --no-langfuse-pod --no-c1-pod
  # Wrapper (export the five ``*_HOST`` first): same --region / --target / --ai-eks-cluster (env: AWS_REGION, JUMPBOX_ID, AI_EKS_CLUSTER). NLB/ALB-only: ``bash deploy/scripts/util/ai_gateway-pf.sh --no-litellm-pod --no-langfuse-pod --no-c1-pod``. With pod autoresolution: drop those three flags.
  # One line, MIDAS + Exlerate (all LB DNS via env; requires ``--with-ai-gateway``):
  python3 deploy/scripts/util/aws-ssm-port-forward-midas-and-ai-gateway.py --profile midas-dev --with-ai-gateway --midas-nlb-host "$NLB_DNS" --midas-alb-host "$ALB_DNS" --litellm-nlb-host "$LITELLM_NLB_HOST" --litellm-alb-host "$LITELLM_ALB_HOST" --langfuse-nlb-host "$LANGFUSE_NLB_HOST" --langfuse-alb-host "$LANGFUSE_ALB_HOST" --c1-alb-host "$C1_ALB_HOST"

  # MIDAS only (same as aws-ssm-port-forward-all.py):
  python3 deploy/scripts/util/aws-ssm-port-forward-midas-and-ai-gateway.py \\
      --midas-nlb-host <midas-nlb-dns>

  # MIDAS + AI Gateway: Exlerate pod DNS/IPs from env or autoresolution (second EKS: exlerate-dev):
  python3 deploy/scripts/util/aws-ssm-port-forward-midas-and-ai-gateway.py \\
      --with-ai-gateway --midas-nlb-host <midas-nlb> \\
      --litellm-nlb-host <eks>-nlb-litellm....amazonaws.com \\
      --litellm-alb-host <litellm-alb-...> \\
      --langfuse-nlb-host <eks>-nlb-langfuse.... \\
      --langfuse-alb-host <langfuse-alb-...> --c1-alb-host <c1-alb-...>

  # All MIDAS NLB+ALB+pod tunnels (legacy all.py example):
  # All tunnels – backend/frontend/graph IPs resolved automatically from EKS:
  python3 deploy/scripts/util/aws-ssm-port-forward-midas-and-ai-gateway.py \\
      --midas-nlb-host <nlb-dns>

  # Backend and NLB only (no kubectl needed for backend if --backend-host is given):
  python3 deploy/scripts/util/aws-ssm-port-forward-midas-and-ai-gateway.py \\
      --no-frontend --no-graph --midas-nlb-host <nlb-dns>

  # Frontend tunnel only – pod IP auto-resolved via SSM on the jumpbox (no local kubectl needed):
  python3 deploy/scripts/util/aws-ssm-port-forward-midas-and-ai-gateway.py \\
      --no-backend --no-graph --no-midas-nlb

  # Frontend tunnel only – supply pod IP explicitly (skips SSM resolution):
  python3 deploy/scripts/util/aws-ssm-port-forward-midas-and-ai-gateway.py \\
      --no-backend --no-graph --no-midas-nlb --no-kubectl \\
      --frontend-host <FRONTEND_POD_IP>

  # Override the backend local port and jumpbox:
  python3 deploy/scripts/util/aws-ssm-port-forward-midas-and-ai-gateway.py \\
      --target i-0abc1234def56789 \\
      --backend-local-port 19081 \\
      --midas-nlb-host <nlb-dns>

After starting, the script prints one line per **active** tunnel with example **local** URLs.
If you used ``--with-ai-gateway``, it also prints a grouped **Exlerate local URL** block;
without that flag, only MIDAS lines appear there.

Press Ctrl+C to stop all tunnels.
"""
from __future__ import annotations

import argparse
import json
import os
import pty
import re
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from typing import Optional

# Force line-buffered stdout/stderr so output appears immediately.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)  # type: ignore[attr-defined]
    sys.stderr.reconfigure(line_buffering=True)  # type: ignore[attr-defined]


# Third-party packages this script needs: (import_name, pip_package_name)
# Add entries here if new dependencies are introduced.
_REQUIRED_PACKAGES: list[tuple[str, str]] = []


def _ensure_packages() -> None:
    """Check all required third-party packages and pip-install any that are missing."""
    missing: list[tuple[str, str]] = []
    for import_name, pip_name in _REQUIRED_PACKAGES:
        try:
            __import__(import_name)
        except ImportError:
            missing.append((import_name, pip_name))

    if not missing:
        return

    pkg_list = ", ".join(pip_name for _, pip_name in missing)
    print(
        f"\nThe following package(s) are required but not installed: {pkg_list}\n"
        "They will be installed into the current Python environment via pip.\n"
        f"  {sys.executable} -m pip install {pkg_list}\n"
    )
    try:
        answer = input("Install now? [y/N] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        answer = ""

    if answer not in ("y", "yes"):
        sys.exit(f"Aborted. Install manually with:\n  pip install {pkg_list}\n")

    for import_name, pip_name in missing:
        print(f"  Installing {pip_name}...")
        # shell=False (default): list-form argv prevents shell metacharacter injection.
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "--quiet", pip_name],
        )
        if result.returncode != 0:
            sys.exit(
                f"ERROR: Failed to install {pip_name} (exit {result.returncode}).\n"
                f"Try manually: pip install {pip_name}\n"
            )
        try:
            __import__(import_name)
        except ImportError:
            sys.exit(
                f"ERROR: {pip_name} installed but '{import_name}' still cannot "
                f"be imported.\nTry opening a new terminal or: pip install {pip_name}\n"
            )
        print(f"  {pip_name} installed successfully.")

    print()


_ensure_packages()

# ---------------------------------------------------------------------------
# MIDAS project defaults – override via CLI flags or env vars
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# CLI input validation — defense-in-depth against Fortify "Command Injection".
#
# Every subprocess call in this script already uses the list form
# (shell=False is the default for subprocess.run / subprocess.Popen with a
# list argv), so shell-metacharacter injection is structurally impossible.
# The regexes below add belt-and-braces input validation so that the AWS CLI
# itself never receives values that could not have come from a legitimate
# operator. Fortify flags the dataflow regardless of shell=False; the
# validation here makes the false-positive nature explicit in code.
# ---------------------------------------------------------------------------
_EC2_ID_RE = re.compile(r"^i-[0-9a-f]{8,17}$")
_PROFILE_RE = re.compile(r"^[a-zA-Z0-9_.-]+$")
_AWS_REGION_RE = re.compile(r"^[a-z]{2}-[a-z]+-\d+$")
_K8S_NS_RE = re.compile(r"^[a-z0-9]([-a-z0-9]{0,61}[a-z0-9])?$")
_EKS_CLUSTER_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9-_]{0,99}$")


def _validate_args(args: argparse.Namespace) -> None:
    """Reject CLI inputs that do not match expected AWS / Kubernetes ID shapes.

    Called once at the top of main() so that no subsequent subprocess call ever
    receives a malformed identifier. Defense-in-depth on top of shell=False.
    """
    if not _EC2_ID_RE.match(args.target):
        sys.exit(
            f"ERROR: --target must be a valid EC2 instance ID (e.g. i-0abc1234def56789); got {args.target!r}.\n"
        )
    if not _AWS_REGION_RE.match(args.region):
        sys.exit(
            f"ERROR: --region must be a valid AWS region string (e.g. us-east-1); got {args.region!r}.\n"
        )
    if args.profile and args.profile.lower() != "default" and not _PROFILE_RE.match(args.profile):
        sys.exit(
            f"ERROR: --profile contains invalid characters (allowed: a-z A-Z 0-9 _ . -); got {args.profile!r}.\n"
        )
    if not _K8S_NS_RE.match(args.namespace):
        sys.exit(
            f"ERROR: --namespace must be a valid Kubernetes namespace; got {args.namespace!r}.\n"
        )
    if not _EKS_CLUSTER_RE.match(args.eks_cluster):
        sys.exit(
            f"ERROR: --eks-cluster must be a valid EKS cluster name; got {args.eks_cluster!r}.\n"
        )
    # ai_eks_cluster is optional — only validate when supplied.
    ai_cluster = getattr(args, "ai_eks_cluster", "") or ""
    if ai_cluster and not _EKS_CLUSTER_RE.match(ai_cluster):
        sys.exit(
            f"ERROR: --ai-eks-cluster must be a valid EKS cluster name; got {ai_cluster!r}.\n"
        )


DEFAULT_TARGET = "i-04231b2a8a4d98b63"
DEFAULT_REGION = "us-east-1"
DEFAULT_NAMESPACE = "midas-apps"
DEFAULT_EKS_CLUSTER = "midas-eks-dev"
# AI Gateway (Exlerate) EKS from ai_gateway/infra/terraform/environment/<env>/terragrunt.hcl (example dev: exlerate-dev)
DEFAULT_AI_GATEWAY_EKS_CLUSTER = "exlerate-dev"
# Namespaces: ai_gateway/infra/terraform/modules/variables.tf
DEFAULT_LITELLM_NAMESPACE = "litellm"
DEFAULT_LANGFUSE_NAMESPACE = "langfuse"
DEFAULT_C1_NAMESPACE = "c1-api"
SSM_DOCUMENT = "AWS-StartPortForwardingSessionToRemoteHost"

# Kubernetes label selectors – each matches the app.kubernetes.io/name label that the
# respective Helm chart stamps on every pod it manages (Chart.Name = service name).
FRONTEND_POD_LABEL = "app.kubernetes.io/name=midas-web-frontend-svc"
BACKEND_POD_LABEL  = "app.kubernetes.io/name=midas-api-backend-svc"
GRAPH_POD_LABEL    = "app.kubernetes.io/name=midas-graph-svc"

# AI Gateway: defaults match ai_gateway/helm (litellm, langfuse, control-api). Override with --*-pod-label.
DEFAULT_LITELLM_POD_LABEL = "app.kubernetes.io/name=litellm"
DEFAULT_LANGFUSE_POD_LABEL = "app.kubernetes.io/name=langfuse-web"
DEFAULT_C1_POD_LABEL = "app.kubernetes.io/name=control-api"

# Env-var overrides (still honoured; auto-resolve is used when these are empty).
BACKEND_NODE_IP = os.environ.get("BACKEND_NODE_IP", "")
FRONTEND_NODE_IP = os.environ.get("FRONTEND_NODE_IP", "")
GRAPH_NODE_IP = os.environ.get("GRAPH_NODE_IP", "")
# MIDAS load balancers (deploy/ecs-app/): prefer MIDAS_* env, fall back to legacy NLB_DNS / ALB_DNS.
NLB_DNS = os.environ.get("NLB_DNS", "")
ALB_DNS = os.environ.get("ALB_DNS", "")
MIDAS_NLB_HOST_DEFAULT = os.environ.get("MIDAS_NLB_HOST", NLB_DNS)
MIDAS_ALB_HOST_DEFAULT = os.environ.get("MIDAS_ALB_HOST", ALB_DNS)

# AI Gateway load balancers (get DNS from console or `aws elbv2 describe-load-balancers`)
LITELLM_NLB_HOST = os.environ.get("LITELLM_NLB_HOST", "")
LITELLM_ALB_HOST = os.environ.get("LITELLM_ALB_HOST", "")
LANGFUSE_NLB_HOST = os.environ.get("LANGFUSE_NLB_HOST", "")
LANGFUSE_ALB_HOST = os.environ.get("LANGFUSE_ALB_HOST", "")
C1_ALB_HOST = os.environ.get("C1_ALB_HOST", "")
# Pod IPs for AI Gateway (optional; kubectl auto-resolve if unset and tunnel enabled)
LITELLM_NODE_IP = os.environ.get("LITELLM_NODE_IP", "")
LANGFUSE_NODE_IP = os.environ.get("LANGFUSE_NODE_IP", "")
C1_NODE_IP = os.environ.get("C1_NODE_IP", "")


@dataclass
class TunnelConfig:
    name: str
    host: str
    remote_port: int
    local_port: int
    enabled: bool = True
    description: str = ""
    hints: list[str] = field(default_factory=list)


def _tunnel_host_flag(name: str) -> str:
    """Map tunnel ``name`` to the argparse long option that supplies the host."""
    if name in (
        "litellm_pod",
        "litellm_nlb",
        "litellm_alb",
        "langfuse_pod",
        "langfuse_nlb",
        "langfuse_alb",
    ):
        return f"--{name.replace('_', '-')}-host"
    if name == "c1_pod":
        return "--c1-pod-host"
    if name == "c1_alb":
        return "--c1-alb-host"
    if name in ("midas_nlb", "midas_alb"):
        return f"--{name.replace('_', '-')}-host"
    return f"--{name}-host"


def _ssm_run(
    aws_exe: str,
    target: str,
    region: str,
    profile: Optional[str],
    shell_cmd: str,
    description: str,
    poll_attempts: int = 20,
    poll_interval: float = 2.0,
) -> str:
    """Send a one-shot shell command to the jumpbox via SSM AWS-RunShellScript.

    Polls for completion and returns stdout on success; calls sys.exit on error.
    *description* is a short label used only in error messages.
    """
    cmd = [aws_exe]
    if profile:
        cmd += ["--profile", profile]
    cmd += [
        "ssm", "send-command",
        "--instance-ids", target,
        "--document-name", "AWS-RunShellScript",
        "--parameters", json.dumps({"commands": [shell_cmd]}),
        "--region", region,
        "--query", "Command.CommandId",
        "--output", "text",
    ]
    # shell=False (default): list-form argv prevents shell metacharacter injection.
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        sys.exit(
            f"ERROR: ssm send-command failed ({description}, exit {result.returncode}).\n"
            f"  stderr: {result.stderr.strip()}\n"
        )
    command_id = result.stdout.strip()
    if not command_id:
        sys.exit(f"ERROR: ssm send-command returned no CommandId ({description}).\n")

    get_cmd = [aws_exe]
    if profile:
        get_cmd += ["--profile", profile]
    get_cmd += [
        "ssm", "get-command-invocation",
        "--command-id", command_id,
        "--instance-id", target,
        "--region", region,
        "--output", "json",
    ]
    for _ in range(poll_attempts):
        time.sleep(poll_interval)
        # shell=False (default): list-form argv prevents shell metacharacter injection.
        inv = subprocess.run(get_cmd, capture_output=True, text=True)
        if inv.returncode != 0:
            continue
        try:
            inv_data = json.loads(inv.stdout)
        except json.JSONDecodeError:
            continue
        status = inv_data.get("Status", "")
        if status in ("Pending", "InProgress", "Delayed"):
            continue
        if status != "Success":
            sys.exit(
                f"ERROR: SSM command ended with status {status!r} ({description}).\n"
                f"  stderr: {inv_data.get('StandardErrorContent','').strip()}\n"
                f"  stdout: {inv_data.get('StandardOutputContent','').strip()[:400]}\n"
            )
        return inv_data.get("StandardOutputContent", "")

    sys.exit(
        f"ERROR: Timed out waiting for SSM command ({description}, ~{int(poll_attempts * poll_interval)}s).\n"
        f"  CommandId: {command_id}\n"
        "Check SSM Run Command history in the AWS console for details.\n"
    )


def configure_jumpbox_kubeconfig(
    aws_exe: str,
    target: str,
    region: str,
    eks_cluster: str,
    profile: Optional[str],
) -> None:
    """Ensure the jumpbox kubeconfig is up-to-date before any kubectl use.

    SSM RunShellScript runs with HOME="" so we set HOME=/root explicitly and
    run 'aws eks update-kubeconfig' on the jumpbox.  This is always called as
    a pre-flight step regardless of whether pod IP auto-resolution is enabled,
    so the jumpbox is ready for any subsequent kubectl invocations.
    """
    print(f"  Configuring kubeconfig on jumpbox (cluster: {eks_cluster}) ...")
    shell_cmd = (
        "export HOME=/root; "
        f"aws eks update-kubeconfig --name {eks_cluster} --region {region} 2>&1"
    )
    output = _ssm_run(
        aws_exe, target, region, profile,
        shell_cmd,
        description=f"update-kubeconfig {eks_cluster}",
    )
    for line in output.strip().splitlines():
        if line.strip():
            print(f"    {line.strip()}")


def resolve_pod_ip_via_ssm(
    service: str,
    label: str,
    namespace: str,
    aws_exe: str,
    target: str,
    region: str,
    profile: Optional[str],
) -> str:
    """Resolve a pod IP by running kubectl on the jumpbox via SSM AWS-RunShellScript.

    Assumes configure_jumpbox_kubeconfig() has already run so HOME and kubeconfig
    are valid on the jumpbox.  jsonpath emits one line per pod: "<phase> <podIP> <name>".

    *service* is a human-readable name used only in messages (e.g. ``"frontend"``).
    *label* is a ``key=value`` selector, e.g. ``FRONTEND_POD_LABEL``.

    Returns the podIP string; exits with a clear error on any failure.
    """
    shell_cmd = (
        "export HOME=/root; "
        f"kubectl get pods -n {namespace} -l '{label}' "
        f"-o jsonpath='{{range .items[*]}}{{.status.phase}} {{.status.podIP}} {{.metadata.name}}\\n{{end}}'"
    )
    print(f"  Resolving {service} pod IP via SSM on jumpbox {target} ...")
    output_text = _ssm_run(
        aws_exe, target, region, profile,
        shell_cmd,
        description=f"resolve-pod-ip {service}",
    )

    # Parse lines: "<phase> <podIP> <name>" (strip any stray newlines/escape noise from SSM)
    def _clean_pod_name(name: str) -> str:
        s = re.sub(r"[\r\n\x00-\x1f\\]+", "", name.strip())
        return s.split()[0] if s else name.strip()

    running_ip = ""
    any_ip = ""
    any_name = ""
    for line in output_text.strip().splitlines():
        parts = line.strip().split()
        if len(parts) >= 3:
            phase, pod_ip, pod_name = (
                parts[0],
                parts[1].strip(),
                _clean_pod_name(" ".join(parts[2:]) if len(parts) > 3 else parts[2]),
            )
            if not any_ip:
                any_ip, any_name = pod_ip, pod_name
            if phase == "Running" and not running_ip:
                running_ip = pod_ip
                print(f"  Found Running {service} pod {pod_name!r} → {pod_ip}")
                break

    chosen_ip = running_ip or any_ip
    if not chosen_ip:
        sys.exit(
            f"ERROR: No {service} pods found via SSM "
            f"(namespace={namespace!r}, label={label!r}).\n"
            f"  Raw output: {output_text.strip()[:400]}\n"
            f"Ensure the {service} deployment is running in the cluster.\n"
        )

    if not running_ip and any_ip:
        print(f"  Warning: no Running {service} pod found; using {any_name!r} → {any_ip}")

    return chosen_ip


_KNOWN_PROFILES = ["midas-dev", "default"]


def _prompt_profile() -> Optional[str]:
    """Interactively ask the user which AWS CLI profile to use.

    Presents three choices:
      1. midas-dev
      2. default  (AWS default credential chain – no --profile flag passed to CLI)
      3. Enter your own profile name

    Returns the chosen profile string, or ``None`` for the AWS default chain.
    Falls back to $AWS_PROFILE / $AWS_DEFAULT_PROFILE silently when stdin is not
    a TTY (e.g. CI / piped execution).
    """
    if not sys.stdin.isatty():
        return os.environ.get("AWS_PROFILE") or os.environ.get("AWS_DEFAULT_PROFILE") or None

    print("\nSelect an AWS CLI profile:")
    print("  1) midas-dev")
    print("  2) default  (AWS default credential chain)")
    print("  3) Enter your own profile name")
    print()

    while True:
        try:
            raw = input("Choice [1/2/3]: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            sys.exit("Aborted.\n")

        if raw == "1":
            print(f"  Using profile: midas-dev\n")
            return "midas-dev"
        elif raw == "2":
            print("  Using profile: default (AWS default credential chain)\n")
            return "default"
        elif raw == "3":
            try:
                custom = input("  Profile name: ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                sys.exit("Aborted.\n")
            if not custom:
                print("  Profile name cannot be empty. Try again.")
                continue
            print(f"  Using profile: {custom}\n")
            return custom
        else:
            print("  Invalid choice – please enter 1, 2, or 3.")


def _apply_ai_gateway_only_mode(args: argparse.Namespace) -> None:
    """``--ai-gateway-only``: only ``ai_gateway``/Exlerate tunnels; all MIDAS tunnels off. Implies --with-ai-gateway."""
    if not args.ai_gateway_only:
        return
    args.with_ai_gateway = True
    args.backend_enabled = False
    args.frontend_enabled = False
    args.graph_enabled = False
    args.midas_nlb_enabled = False
    args.midas_alb_enabled = False


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="""Start SSM port-forward tunnel(s) through the MIDAS jumpbox to VPC targets.

  • At least one tunnel must remain enabled (after all --no-* flags), or the script
    exits with an error and creates no sessions.
  • Default: MIDAS EKS (midas-eks-dev) backend/frontend/graph + optional MIDAS NLB/ALB.
  • Exlerate (ai_gateway in this repo): add --with-ai-gateway for LiteLLM / Langfuse
    (NLB→ALB and pod) and C1 (ALB + pod), or use --ai-gateway-only to run **only** that
    stack (all MIDAS tunnels off). Requires second EKS (default exlerate-dev) for pod
    autoresolution when pod hosts are not set.
  • With --with-ai-gateway (or --ai-gateway-only), the run ends with a printed ai_gateway
    local URL map; without that, only MIDAS lines appear in the summary.

  Full narrative, port tables, and examples: see the epilog below (same as this file's
  module docstring).""",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    # ── Shared / jumpbox ────────────────────────────────────────────────────
    shared = parser.add_argument_group("shared / jumpbox")
    shared.add_argument(
        "--target",
        default=DEFAULT_TARGET,
        metavar="INSTANCE_ID",
        help=f"Jumpbox EC2 instance ID (default: {DEFAULT_TARGET})",
    )
    shared.add_argument(
        "--region",
        default=DEFAULT_REGION,
        metavar="REGION",
        help=f"AWS region (default: {DEFAULT_REGION})",
    )
    shared.add_argument(
        "--profile",
        default=None,
        metavar="PROFILE",
        help=(
            "AWS CLI profile to use. When not supplied the script prompts you to "
            "choose from: midas-dev, default, or enter your own. "
            "Pass --profile default to skip the prompt and use the default profile. "
            "Override silently via $AWS_PROFILE env var (only used when --profile is "
            "not given AND the interactive prompt is suppressed by a non-TTY stdin)."
        ),
    )
    shared.add_argument(
        "--namespace",
        default=DEFAULT_NAMESPACE,
        metavar="NAMESPACE",
        help=f"Kubernetes namespace for MIDAS pods (default: {DEFAULT_NAMESPACE})",
    )
    shared.add_argument(
        "--eks-cluster",
        default=DEFAULT_EKS_CLUSTER,
        metavar="CLUSTER_NAME",
        help=(
            f"EKS cluster name used to refresh the kubeconfig on the jumpbox "
            f"(default: {DEFAULT_EKS_CLUSTER}). The script always runs "
            f"'aws eks update-kubeconfig' on the jumpbox before any pod IP "
            f"resolution or tunnel is started."
        ),
    )
    shared.add_argument(
        "--no-kubectl",
        dest="use_kubectl",
        action="store_false",
        default=True,
        help=(
            "Skip automatic pod IP resolution for all tunnels. "
            "By default the script resolves pod IPs by running kubectl on the jumpbox "
            "via SSM (no local kubectl required). Use --no-kubectl only when you want "
            "to supply --<service>-host values yourself and skip the SSM lookup entirely. "
            "Note: the jumpbox kubeconfig is always refreshed regardless of this flag."
        ),
    )

    # ── Backend tunnel ───────────────────────────────────────────────────────
    be = parser.add_argument_group("backend tunnel")
    be.add_argument(
        "--no-backend",
        dest="backend_enabled",
        action="store_false",
        default=True,
        help="Disable the backend tunnel (default: enabled)",
    )
    be.add_argument(
        "--backend-host",
        default=BACKEND_NODE_IP,
        metavar="IP",
        help=(
            "Backend pod IP. When not set (and --no-kubectl is not used) the IP is "
            "resolved automatically from the first Running EKS pod with label "
            f"{BACKEND_POD_LABEL!r}. "
            f"Falls back to BACKEND_NODE_IP env var ({BACKEND_NODE_IP!r} if set)."
        ),
    )
    be.add_argument(
        "--backend-port",
        type=int,
        default=8000,
        metavar="PORT",
        help="Remote port on the backend pod (default: 8000)",
    )
    be.add_argument(
        "--backend-local-port",
        type=int,
        default=9081,
        metavar="LOCAL_PORT",
        help="Local port for the backend tunnel (default: 9081)",
    )

    # ── Frontend tunnel ──────────────────────────────────────────────────────
    fe = parser.add_argument_group("frontend tunnel")
    fe.add_argument(
        "--no-frontend",
        dest="frontend_enabled",
        action="store_false",
        default=True,
        help="Disable the frontend tunnel (default: enabled)",
    )
    fe.add_argument(
        "--frontend-host",
        default=FRONTEND_NODE_IP,
        metavar="IP",
        help=(
            "Frontend pod IP. When not set (and --no-kubectl is not used) the IP is "
            "resolved automatically from the first Running EKS pod with label "
            f"{FRONTEND_POD_LABEL!r}. "
            f"Falls back to FRONTEND_NODE_IP env var ({FRONTEND_NODE_IP!r} if set)."
        ),
    )
    fe.add_argument(
        "--frontend-port",
        type=int,
        default=8080,
        metavar="PORT",
        help="Remote port on the frontend pod (default: 8080)",
    )
    fe.add_argument(
        "--frontend-local-port",
        type=int,
        default=9000,
        metavar="LOCAL_PORT",
        help="Local port for the frontend tunnel (default: 9000)",
    )

    # ── Graph tunnel ─────────────────────────────────────────────────────────
    gr = parser.add_argument_group("graph tunnel")
    gr.add_argument(
        "--no-graph",
        dest="graph_enabled",
        action="store_false",
        default=True,
        help="Disable the graph tunnel (default: enabled)",
    )
    gr.add_argument(
        "--graph-host",
        default=GRAPH_NODE_IP,
        metavar="IP",
        help=(
            "Graph pod IP. When not set (and --no-kubectl is not used) the IP is "
            "resolved automatically from the first Running EKS pod with label "
            f"{GRAPH_POD_LABEL!r}. "
            f"Falls back to GRAPH_NODE_IP env var ({GRAPH_NODE_IP!r} if set)."
        ),
    )
    gr.add_argument(
        "--graph-port",
        type=int,
        default=8001,
        metavar="PORT",
        help=(
            "Remote port on the graph pod (default: 8001). Matches "
            "midas-graph-svc containerPort and the ALB graph target group."
        ),
    )
    gr.add_argument(
        "--graph-local-port",
        type=int,
        default=9083,
        metavar="LOCAL_PORT",
        help="Local port for the graph tunnel (default: 9083)",
    )

    # ── MIDAS NLB / MIDAS ALB (deploy/ecs-app) — not Exlerate; see litellm-*/langfuse-* for AI Gateway
    nlb = parser.add_argument_group(
        "MIDAS NLB tunnel (private NLB → MIDAS ALB, deploy/ecs-app)",
    )
    nlb.add_argument(
        "--no-midas-nlb", "--no-nlb",
        dest="midas_nlb_enabled",
        action="store_false",
        default=True,
        help="Disable the MIDAS NLB tunnel (default: on). Alias: --no-nlb.",
    )
    nlb.add_argument(
        "--midas-nlb-host", "--nlb-host",
        dest="midas_nlb_host",
        default=MIDAS_NLB_HOST_DEFAULT,
        metavar="DNS_NAME",
        help=(
            "MIDAS (application) internal NLB DNS, not an Exlerate/AI NLB. "
            f"Default: MIDAS_NLB_HOST, else NLB_DNS (currently {MIDAS_NLB_HOST_DEFAULT!r}). "
            "Get with: cd deploy/ecs-app && terraform output -raw nlb_dns_name. "
            "Alias: --nlb-host."
        ),
    )
    nlb.add_argument(
        "--midas-nlb-port", "--nlb-port",
        dest="midas_nlb_port",
        type=int,
        default=443,
        metavar="PORT",
        help="Remote port on the MIDAS NLB (default: 443). Alias: --nlb-port.",
    )
    nlb.add_argument(
        "--midas-nlb-local-port", "--nlb-local-port",
        dest="midas_nlb_local_port",
        type=int,
        default=9082,
        metavar="LOCAL_PORT",
        help="Local port for the MIDAS NLB tunnel (default: 9082). Alias: --nlb-local-port.",
    )

    # The ALB is the HTTPS termination point (ACM cert on port 443). Tunneling
    # here lets you exercise the ALB path-routing rules (/frontend /backend
    # /graph) directly, bypassing the NLB pass-through layer.
    alb = parser.add_argument_group(
        "MIDAS ALB tunnel (HTTPS, path /frontend|/backend|/graph) — not litellm/langfuse/c1",
    )
    alb.add_argument(
        "--no-midas-alb", "--no-alb",
        dest="midas_alb_enabled",
        action="store_false",
        default=True,
        help="Disable the MIDAS ALB tunnel. Alias: --no-alb.",
    )
    alb.add_argument(
        "--midas-alb-host", "--alb-host",
        dest="midas_alb_host",
        default=MIDAS_ALB_HOST_DEFAULT,
        metavar="DNS_NAME",
        help=(
            "MIDAS internal ALB DNS, not a LiteLLM/Langfuse/C1 ALB. "
            f"Default: MIDAS_ALB_HOST, else ALB_DNS (currently {MIDAS_ALB_HOST_DEFAULT!r}). "
            "Get with: cd deploy/ecs-app && terraform output -raw alb_dns_name. "
            "Alias: --alb-host."
        ),
    )
    alb.add_argument(
        "--midas-alb-port", "--alb-port",
        dest="midas_alb_port",
        type=int,
        default=443,
        metavar="PORT",
        help="Remote port on the MIDAS ALB HTTPS listener (default: 443). Alias: --alb-port.",
    )
    alb.add_argument(
        "--midas-alb-local-port", "--alb-local-port",
        dest="midas_alb_local_port",
        type=int,
        default=9084,
        metavar="LOCAL_PORT",
        help="Local port for the MIDAS ALB tunnel (default: 9084). Alias: --alb-local-port.",
    )

    # ── AI Gateway (ai_gateway submodule) / Exlerate EKS ──────────────────
    ai = parser.add_argument_group(
        "ai_gateway (Exlerate) — EKS, namespaces, LiteLLM / Langfuse / C1",
    )
    ai.add_argument(
        "--with-ai-gateway",
        action="store_true",
        help=(
            "Opt in to AI Gateway (Exlerate) tunnels. Without this flag only MIDAS "
            "tunnels run. When set, Exlerate NLB/ALB and pod-direct tunnels are enabled "
            "unless individually disabled with --no-litellm-*, --no-langfuse-*, --no-c1-*."
        ),
    )
    ai.add_argument(
        "--ai-gateway-only",
        action="store_true",
        dest="ai_gateway_only",
        help=(
            "Run only the ai_gateway stack: turns off all MIDAS tunnels, implies "
            "--with-ai-gateway, and shows the ai_gateway local URL block. You still pass "
            "Exlerate hostnames (or env) for the tunnels you need; add --no-litellm-* as "
            "required to match your scope."
        ),
    )
    ai.add_argument(
        "--ai-eks-cluster",
        default=DEFAULT_AI_GATEWAY_EKS_CLUSTER,
        metavar="CLUSTER_NAME",
        help=(
            "EKS cluster name for AI Gateway (LiteLLM / Langfuse / C1). The script "
            "runs 'aws eks update-kubeconfig' for this cluster after MIDAS to resolve "
            f"AI pod IPs (default: {DEFAULT_AI_GATEWAY_EKS_CLUSTER})."
        ),
    )
    ai.add_argument(
        "--no-ai-kubeconfig",
        dest="ai_kubeconfig_enabled",
        action="store_false",
        default=True,
        help=(
            "Do not run aws eks update-kubeconfig for the AI cluster (use if you have "
            "no access to Exlerate or only use MDNS/ALB tunnels for AI). Pod IP "
            "autoresolution for AI will fail without a valid kubeconfig."
        ),
    )
    ai.add_argument(
        "--litellm-namespace",
        default=DEFAULT_LITELLM_NAMESPACE,
        metavar="NS",
        help=f"K8s namespace for LiteLLM (default: {DEFAULT_LITELLM_NAMESPACE!r})",
    )
    ai.add_argument(
        "--langfuse-namespace",
        default=DEFAULT_LANGFUSE_NAMESPACE,
        metavar="NS",
        help=f"K8s namespace for Langfuse (default: {DEFAULT_LANGFUSE_NAMESPACE!r})",
    )
    ai.add_argument(
        "--c1-namespace",
        default=DEFAULT_C1_NAMESPACE,
        metavar="NS",
        help=f"K8s namespace for C1 (control API) (default: {DEFAULT_C1_NAMESPACE!r})",
    )
    ai.add_argument(
        "--litellm-pod-label",
        default=DEFAULT_LITELLM_POD_LABEL,
        metavar="KEY=VALUE",
        help=(
            "Label selector for LiteLLM pod IP resolution. Default matches "
            f"ai_gateway helm chart conventions ({DEFAULT_LITELLM_POD_LABEL!r})."
        ),
    )
    ai.add_argument(
        "--langfuse-pod-label",
        default=DEFAULT_LANGFUSE_POD_LABEL,
        metavar="KEY=VALUE",
        help=(
            "Label selector for Langfuse web pod IP resolution. If no pods are found, "
            "set this to your chart’s labels (default "
            f"{DEFAULT_LANGFUSE_POD_LABEL!r})."
        ),
    )
    ai.add_argument(
        "--c1-pod-label",
        default=DEFAULT_C1_POD_LABEL,
        metavar="KEY=VALUE",
        help=(
            "Label selector for control-api pod IP resolution (default "
            f"{DEFAULT_C1_POD_LABEL!r})."
        ),
    )

    ltm = parser.add_argument_group("AI Gateway: LiteLLM (pod + litellm NLB/ALB)")
    ltm.add_argument(
        "--no-litellm-pod",
        dest="litellm_pod_enabled",
        action="store_false",
        default=True,
        help="Disable LiteLLM pod-direct tunnel (default: enabled)",
    )
    ltm.add_argument(
        "--litellm-pod-host",
        default=LITELLM_NODE_IP,
        metavar="IP",
        help="LiteLLM pod IP; falls back to LITELLM_NODE_IP env (default empty).",
    )
    ltm.add_argument(
        "--litellm-pod-port",
        type=int,
        default=4000,
        metavar="PORT",
        help="Remote HTTP port (default: 4000; ai_gateway/helm/litellm/values.yaml).",
    )
    ltm.add_argument(
        "--litellm-pod-local-port",
        type=int,
        default=9190,
        metavar="PORT",
        help="Local port for LiteLLM pod (default: 9190)",
    )
    ltm.add_argument(
        "--no-litellm-nlb",
        dest="litellm_nlb_enabled",
        action="store_false",
        default=True,
        help="Disable LiteLLM NLB tunnel (default: enabled)",
    )
    ltm.add_argument(
        "--litellm-nlb-host",
        default=LITELLM_NLB_HOST,
        metavar="DNS",
        help="Internal NLB DNS (exlerate AI Gateway, litellm NLB) — LITELLM_NLB_HOST.",
    )
    ltm.add_argument(
        "--litellm-nlb-port",
        type=int,
        default=443,
        metavar="PORT",
        help="Remote NLB listener port (default: 443, ai_gateway alb.tf nlb_443).",
    )
    ltm.add_argument(
        "--litellm-nlb-local-port",
        type=int,
        default=9191,
        metavar="PORT",
        help="Local port for LiteLLM NLB (default: 9191)",
    )
    ltm.add_argument(
        "--no-litellm-alb",
        dest="litellm_alb_enabled",
        action="store_false",
        default=True,
        help="Disable LiteLLM ALB tunnel (default: enabled)",
    )
    ltm.add_argument(
        "--litellm-alb-host",
        default=LITELLM_ALB_HOST,
        metavar="DNS",
        help="LiteLLM ALB (ingress group litellm) — LITELLM_ALB_HOST.",
    )
    ltm.add_argument(
        "--litellm-alb-port",
        type=int,
        default=443,
        metavar="PORT",
        help="Remote port on the LiteLLM ALB (default: 443)",
    )
    ltm.add_argument(
        "--litellm-alb-local-port",
        type=int,
        default=9192,
        metavar="PORT",
        help="Local port for LiteLLM ALB (default: 9192)",
    )

    lgf = parser.add_argument_group("AI Gateway: Langfuse (pod + langfuse NLB/ALB)")
    lgf.add_argument(
        "--no-langfuse-pod",
        dest="langfuse_pod_enabled",
        action="store_false",
        default=True,
    )
    lgf.add_argument(
        "--langfuse-pod-host",
        default=LANGFUSE_NODE_IP,
        metavar="IP",
        help="Langfuse web pod IP; LANGFUSE_NODE_IP env if unset.",
    )
    lgf.add_argument(
        "--langfuse-pod-port",
        type=int,
        default=3000,
        metavar="PORT",
        help="Remote HTTP port (default: 3000, langfuse web).",
    )
    lgf.add_argument(
        "--langfuse-pod-local-port",
        type=int,
        default=9200,
        metavar="PORT",
        help="Local port (default: 9200)",
    )
    lgf.add_argument(
        "--no-langfuse-nlb",
        dest="langfuse_nlb_enabled",
        action="store_false",
        default=True,
    )
    lgf.add_argument(
        "--langfuse-nlb-host",
        default=LANGFUSE_NLB_HOST,
        metavar="DNS",
        help="Internal NLB DNS (langfuse NLB) — LANGFUSE_NLB_HOST.",
    )
    lgf.add_argument(
        "--langfuse-nlb-port",
        type=int,
        default=443,
        metavar="PORT",
    )
    lgf.add_argument(
        "--langfuse-nlb-local-port",
        type=int,
        default=9201,
        metavar="PORT",
    )
    lgf.add_argument(
        "--no-langfuse-alb",
        dest="langfuse_alb_enabled",
        action="store_false",
        default=True,
    )
    lgf.add_argument(
        "--langfuse-alb-host",
        default=LANGFUSE_ALB_HOST,
        metavar="DNS",
        help="Langfuse ALB — LANGFUSE_ALB_HOST.",
    )
    lgf.add_argument(
        "--langfuse-alb-port",
        type=int,
        default=443,
        metavar="PORT",
    )
    lgf.add_argument(
        "--langfuse-alb-local-port",
        type=int,
        default=9202,
        metavar="PORT",
    )

    c1g = parser.add_argument_group("AI Gateway: C1 (control API) — pod + ALB only (no NLB in Terraform)")
    c1g.add_argument(
        "--no-c1-pod",
        dest="c1_pod_enabled",
        action="store_false",
        default=True,
    )
    c1g.add_argument(
        "--c1-pod-host",
        default=C1_NODE_IP,
        metavar="IP",
    )
    c1g.add_argument(
        "--c1-pod-port",
        type=int,
        default=9001,
        metavar="PORT",
        help="Container port (default: 9001, control-api values).",
    )
    c1g.add_argument(
        "--c1-pod-local-port",
        type=int,
        default=9210,
        metavar="PORT",
    )
    c1g.add_argument(
        "--no-c1-alb",
        dest="c1_alb_enabled",
        action="store_false",
        default=True,
    )
    c1g.add_argument(
        "--c1-alb-host",
        default=C1_ALB_HOST,
        metavar="DNS",
        help="C1 (control API) ALB (ingress group control-api) — C1_ALB_HOST.",
    )
    c1g.add_argument(
        "--c1-alb-port",
        type=int,
        default=443,
        metavar="PORT",
    )
    c1g.add_argument(
        "--c1-alb-local-port",
        type=int,
        default=9211,
        metavar="PORT",
    )

    args = parser.parse_args()
    _apply_ai_gateway_only_mode(args)
    return args


def build_tunnel_configs(args: argparse.Namespace) -> list[TunnelConfig]:
    return [
        TunnelConfig(
            name="backend",
            host=args.backend_host,
            remote_port=args.backend_port,
            local_port=args.backend_local_port,
            enabled=args.backend_enabled,
            description="backend API pod",
            hints=[
                f"  Health : http://localhost:{args.backend_local_port}/health",
                f"  Swagger: http://localhost:{args.backend_local_port}/docs",
            ],
        ),
        TunnelConfig(
            name="frontend",
            host=args.frontend_host,
            remote_port=args.frontend_port,
            local_port=args.frontend_local_port,
            enabled=args.frontend_enabled,
            description="frontend pod (direct)",
            hints=[
                f"  UI     : http://localhost:{args.frontend_local_port}/",
                f"  Health : http://localhost:{args.frontend_local_port}/health",
            ],
        ),
        TunnelConfig(
            name="graph",
            host=args.graph_host,
            remote_port=args.graph_port,
            local_port=args.graph_local_port,
            enabled=args.graph_enabled,
            description="graph (GraphRAG) pod",
            hints=[
                f"  Health : http://localhost:{args.graph_local_port}/health",
            ],
        ),
        TunnelConfig(
            name="midas_nlb",
            host=args.midas_nlb_host,
            remote_port=args.midas_nlb_port,
            local_port=args.midas_nlb_local_port,
            enabled=args.midas_nlb_enabled,
            description="MIDAS NLB TCP:443 (pass-through to MIDAS ALB — not Exlerate)",
            hints=[
                f"  UI     : https://localhost:{args.midas_nlb_local_port}/frontend/",
                f"  Backend: https://localhost:{args.midas_nlb_local_port}/backend/health",
                f"  Graph  : https://localhost:{args.midas_nlb_local_port}/graph/health",
            ],
        ),
        TunnelConfig(
            name="midas_alb",
            host=args.midas_alb_host,
            remote_port=args.midas_alb_port,
            local_port=args.midas_alb_local_port,
            enabled=args.midas_alb_enabled,
            description="MIDAS ALB HTTPS:443 (TLS, path to pods — not litellm/langfuse)",
            hints=[
                f"  UI     : https://localhost:{args.midas_alb_local_port}/frontend/",
                f"  Backend: https://localhost:{args.midas_alb_local_port}/backend/health",
                f"  Graph  : https://localhost:{args.midas_alb_local_port}/graph/health",
            ],
        ),
        # ── Exlerate / AI Gateway (see ai_gateway/infra/terraform/modules/alb.tf) ──
        TunnelConfig(
            name="litellm_pod",
            host=args.litellm_pod_host,
            remote_port=args.litellm_pod_port,
            local_port=args.litellm_pod_local_port,
            enabled=args.with_ai_gateway and args.litellm_pod_enabled,
            description="LiteLLM pod direct (port 4000, litellm namespace)",
            hints=[
                f"  http://localhost:{args.litellm_pod_local_port}/",
                f"  http://localhost:{args.litellm_pod_local_port}/health/liveliness",
            ],
        ),
        TunnelConfig(
            name="litellm_nlb",
            host=args.litellm_nlb_host,
            remote_port=args.litellm_nlb_port,
            local_port=args.litellm_nlb_local_port,
            enabled=args.with_ai_gateway and args.litellm_nlb_enabled,
            description="Exlerate internal NLB → ALB (litellm) TCP:443",
            hints=[
                f"  https://localhost:{args.litellm_nlb_local_port}/  (VPC: NLB:443 → litellm ALB:443)",
            ],
        ),
        TunnelConfig(
            name="litellm_alb",
            host=args.litellm_alb_host,
            remote_port=args.litellm_alb_port,
            local_port=args.litellm_alb_local_port,
            enabled=args.with_ai_gateway and args.litellm_alb_enabled,
            description="LiteLLM ALB (ingress group litellm) HTTPS:443",
            hints=[
                f"  https://localhost:{args.litellm_alb_local_port}/  (ALB:443, TLS, group litellm)",
            ],
        ),
        TunnelConfig(
            name="langfuse_pod",
            host=args.langfuse_pod_host,
            remote_port=args.langfuse_pod_port,
            local_port=args.langfuse_pod_local_port,
            enabled=args.with_ai_gateway and args.langfuse_pod_enabled,
            description="Langfuse web pod (port 3000)",
            hints=[
                f"  http://localhost:{args.langfuse_pod_local_port}/",
            ],
        ),
        TunnelConfig(
            name="langfuse_nlb",
            host=args.langfuse_nlb_host,
            remote_port=args.langfuse_nlb_port,
            local_port=args.langfuse_nlb_local_port,
            enabled=args.with_ai_gateway and args.langfuse_nlb_enabled,
            description="Exlerate internal NLB → ALB (langfuse) TCP:443",
            hints=[
                f"  https://localhost:{args.langfuse_nlb_local_port}/  (VPC: NLB:443 → langfuse ALB:443)",
            ],
        ),
        TunnelConfig(
            name="langfuse_alb",
            host=args.langfuse_alb_host,
            remote_port=args.langfuse_alb_port,
            local_port=args.langfuse_alb_local_port,
            enabled=args.with_ai_gateway and args.langfuse_alb_enabled,
            description="Langfuse ALB (ingress group langfuse) HTTPS:443",
            hints=[
                f"  https://localhost:{args.langfuse_alb_local_port}/api/public/health  (ALB, group langfuse)",
            ],
        ),
        TunnelConfig(
            name="c1_pod",
            host=args.c1_pod_host,
            remote_port=args.c1_pod_port,
            local_port=args.c1_pod_local_port,
            enabled=args.with_ai_gateway and args.c1_pod_enabled,
            description="C1 (control API) pod (port 9001, c1-api namespace)",
            hints=[
                f"  http://localhost:{args.c1_pod_local_port}/healthcheck/",
            ],
        ),
        TunnelConfig(
            name="c1_alb",
            host=args.c1_alb_host,
            remote_port=args.c1_alb_port,
            local_port=args.c1_alb_local_port,
            enabled=args.with_ai_gateway and args.c1_alb_enabled,
            description="C1 (control API) ALB (ingress group control-api) — no NLB in Terraform",
            hints=[
                f"  https://localhost:{args.c1_alb_local_port}/  (ALB:443, C1; no Exlerate NLB)",
            ],
        ),
    ]


def validate_tunnels(tunnels: list[TunnelConfig]) -> None:
    active = [t for t in tunnels if t.enabled]
    if not active:
        sys.stderr.write(
            "ERROR: no SSM port-forwards will be created — every tunnel is turned off. "
            "You must keep at least one of: backend, frontend, graph, midas_nlb, or midas_alb, "
            "or pass --with-ai-gateway or --ai-gateway-only and enable at least one Exlerate tunnel. "
            "Check your --no-* flags. Run with -h to see the full list.\n"
        )
        sys.exit(2)

    errors: list[str] = []
    for t in active:
        if not t.host:
            flag = _tunnel_host_flag(t.name)
            errors.append(
                f"  {t.name}: {flag} is required (no default / env var set)"
            )
    if errors:
        sys.stderr.write("ERROR: missing host for enabled tunnel(s):\n")
        for e in errors:
            sys.stderr.write(e + "\n")
        sys.stderr.write(
            "\nDisable unneeded tunnels with the matching --no-* flag or set the host.\n"
        )
        sys.exit(2)


def print_exlerate_url_reference(args: argparse.Namespace) -> None:
    """Log Exlerate / AI Gateway default local URLs and VPC path, when --with-ai-gateway is set.

    The per-tunnel list above is authoritative for which ports are live; this block
    is a static cheat sheet (respects *-local-port overrides on ``args``).
    """
    lp, nl, al = args.litellm_pod_local_port, args.litellm_nlb_local_port, args.litellm_alb_local_port
    gp, gnl, gal = args.langfuse_pod_local_port, args.langfuse_nlb_local_port, args.langfuse_alb_local_port
    cp, calb = args.c1_pod_local_port, args.c1_alb_local_port
    print("\n" + "─" * 60)
    print("ai_gateway (Exlerate) — local URL reference (use only ports you started above)")
    print("  In VPC, NLB listeners:443 forward to the matching internal ALB:443 (ai_gateway Terraform).")
    print("  C1: ALB only in that module — no C1 NLB; use pod tunnel or c1_alb (localhost).")
    print("  Default localhost map (change with --*-local-port):")
    print(f"    LiteLLM   pod  http://localhost:{lp}/   health  http://localhost:{lp}/health/liveliness")
    print(f"              nlb  https://localhost:{nl}/            (target: litellm ALB)")
    print(f"              alb  https://localhost:{al}/            (ingress group: litellm)")
    print(f"    Langfuse  pod  http://localhost:{gp}/")
    print(f"              nlb  https://localhost:{gnl}/            (target: langfuse ALB)")
    print(f"              alb  https://localhost:{gal}/            (e.g. …/api/public/health)")
    print(f"    C1        pod  http://localhost:{cp}/healthcheck/")
    print(f"              alb  https://localhost:{calb}/")


def check_aws_cli() -> str:
    aws_exe = shutil.which("aws")
    if not aws_exe:
        sys.stderr.write(
            "ERROR: AWS CLI not found on PATH.\n"
            "Install: https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html\n"
        )
        sys.exit(2)
    return aws_exe


def _is_apple_silicon() -> bool:
    """Return True when running on Apple Silicon hardware (even under Rosetta 2)."""
    try:
        result = subprocess.run(
            ["sysctl", "-n", "hw.optional.arm64"],
            capture_output=True, text=True,
        )
        return result.stdout.strip() == "1"
    except Exception:
        return False


def _install_session_manager_plugin() -> None:
    """Install the AWS Session Manager plugin via Homebrew (Apple Silicon Mac only)."""
    import platform

    system = platform.system()

    if system != "Darwin":
        sys.exit(
            f"ERROR: Automatic install is only supported on Apple Silicon Macs.\n"
            f"Detected platform: {system}.\n"
            "Install manually: https://docs.aws.amazon.com/systems-manager/latest/userguide/"
            "session-manager-working-with-install-plugin.html\n"
        )

    if not _is_apple_silicon():
        sys.exit(
            "ERROR: Automatic install is only supported on Apple Silicon Macs.\n"
            "This machine does not appear to be Apple Silicon.\n"
            "Install manually: https://docs.aws.amazon.com/systems-manager/latest/userguide/"
            "session-manager-working-with-install-plugin.html\n"
        )

    brew = shutil.which("brew")
    if not brew:
        sys.exit(
            "ERROR: Homebrew (brew) not found on PATH.\n"
            "Install Homebrew first: https://brew.sh\n"
            "Then re-run this script.\n"
        )

    # Ensure brew has downloaded the cask (it will say "already installed" if
    # it was previously attempted – that's fine, we just need the .pkg on disk).
    home = os.path.expanduser("~")
    print("  Fetching session-manager-plugin cask via Homebrew (arm64)...")
    env = os.environ.copy()
    subprocess.run(
        ["arch", "-arm64", brew, "fetch", "--cask", "session-manager-plugin"],
        check=True,
        env=env,
    )

    # Locate the .pkg in the Caskroom cache.
    caskroom = "/opt/homebrew/Caskroom/session-manager-plugin"
    pkg_path: Optional[str] = None
    for root, _, files in os.walk(caskroom):
        for fname in files:
            if fname.endswith(".pkg"):
                pkg_path = os.path.join(root, fname)
                break
        if pkg_path:
            break

    if not pkg_path:
        sys.exit(
            f"ERROR: Could not find session-manager-plugin.pkg under {caskroom}.\n"
            "Try: arch -arm64 brew fetch --cask session-manager-plugin\n"
        )

    # Extract the binary from the .pkg payload directly into ~/.local/bin so
    # no admin/sudo is required.  A .pkg is a xar archive; each component
    # inside contains a gzipped cpio stream named 'Payload'.
    import tempfile
    import tarfile

    dest_bin = os.path.join(home, ".local", "bin")
    os.makedirs(dest_bin, exist_ok=True)
    binary_name = "session-manager-plugin"
    dest_binary = os.path.join(dest_bin, binary_name)

    print(f"  Extracting binary from pkg into {dest_bin} (no admin required)...")
    with tempfile.TemporaryDirectory() as tmpdir:
        # Expand the xar archive.
        subprocess.run(["xar", "-xf", pkg_path, "-C", tmpdir], check=True)

        # Find the 'Payload' file (gzipped cpio) inside any sub-package.
        payload_path: Optional[str] = None
        for root, _, files in os.walk(tmpdir):
            if "Payload" in files:
                payload_path = os.path.join(root, "Payload")
                break

        if not payload_path:
            sys.exit("ERROR: Could not find Payload inside the pkg archive.\n")

        # The Payload is a gzipped cpio stream; extract the specific binary.
        cpio_proc = subprocess.Popen(
            ["cpio", "-i", "--to-stdout",
             f"./usr/local/sessionmanagerplugin/bin/{binary_name}"],
            stdin=open(payload_path, "rb"),
            stdout=open(dest_binary, "wb"),
            stderr=subprocess.DEVNULL,
        )
        cpio_proc.wait()

    if not os.path.isfile(dest_binary):
        sys.exit(
            f"ERROR: Extraction finished but {dest_binary} was not created.\n"
            "Please install the plugin manually:\n"
            "  https://docs.aws.amazon.com/systems-manager/latest/userguide/"
            "session-manager-working-with-install-plugin.html\n"
        )

    os.chmod(dest_binary, 0o755)

    # Patch PATH for this process so the aws CLI subprocess finds it immediately.
    os.environ["PATH"] = dest_bin + ":" + os.environ.get("PATH", "")

    # Persist PATH export to ~/.zshrc if not already present.
    zshrc = os.path.join(home, ".zshrc")
    path_export = f'export PATH="{dest_bin}:$PATH"'
    try:
        existing = open(zshrc).read() if os.path.exists(zshrc) else ""
        if dest_bin not in existing:
            with open(zshrc, "a") as fh:
                fh.write(
                    f"\n# Added by aws-ssm-port-forward-midas-and-ai-gateway.py\n"
                    f"{path_export}\n"
                )
            print(f"  Added PATH export to {zshrc} – run 'source ~/.zshrc' in future shells.\n")
    except OSError:
        pass

    print(f"  session-manager-plugin installed to {dest_binary}\n")


def check_session_manager_plugin() -> None:
    if shutil.which("session-manager-plugin"):
        return

    print(
        "\nThe AWS Session Manager plugin (session-manager-plugin) is required\n"
        "but was not found on PATH. The AWS CLI delegates SSM port-forwarding\n"
        "sessions to this plugin.\n"
        "\nReference: https://docs.aws.amazon.com/systems-manager/latest/userguide/"
        "session-manager-working-with-install-plugin.html\n"
    )
    try:
        answer = input("Install it now? [y/N] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        answer = ""

    if answer not in ("y", "yes"):
        sys.exit(
            "Aborted. Install session-manager-plugin manually and re-run this script.\n"
        )

    print()
    try:
        _install_session_manager_plugin()
    except subprocess.CalledProcessError as exc:
        sys.exit(f"ERROR: Installation failed (exit {exc.returncode}).\n")


def _resolve_host(host: str) -> str:
    """Resolve a hostname to an IPv4 address."""
    if re.match(r"^\d+\.\d+\.\d+\.\d+$", host):
        return host
    try:
        ip = socket.gethostbyname(host)
        print(f"  Resolved {host} → {ip}")
        return ip
    except socket.gaierror:
        return host


def _signal_tunnel_children(leader_pid: int, sig: int) -> None:
    """Send *sig* to every process in the tunnel child's POSIX process group.

    ``start_tunnel`` uses ``Popen(..., start_new_session=True)`` so the ``aws`` CLI
    owns a new session and PTY.  It then execs / forks ``session-manager-plugin`` in
    the same process group.  ``Popen.terminate()`` only signals the ``aws`` PID; the
    plugin keeps running and the local port stays bound until the user kills it by hand.
    """
    if not hasattr(os, "killpg"):
        try:
            os.kill(leader_pid, sig)
        except ProcessLookupError:
            pass
        return
    try:
        pgid = os.getpgid(leader_pid)
    except ProcessLookupError:
        return
    try:
        os.killpg(pgid, sig)
    except ProcessLookupError:
        pass
    except PermissionError:
        try:
            os.kill(leader_pid, sig)
        except ProcessLookupError:
            pass


def _diagnose_and_exit(name: str, output: str) -> None:
    if "403" in output or "Forbidden" in output or "authentication failed" in output:
        sys.exit(
            f"\nERROR: [{name}] AWS credentials expired or insufficient permissions.\n"
            "Run:   aws sso login --profile midas-dev\n"
            f"Detail: {output.strip()}\n"
        )
    sys.exit(
        f"\nERROR: [{name}] SSM session exited before becoming ready.\n"
        f"Output: {output.strip() or '(none)'}\n"
        "Check: aws sso login --profile midas-dev\n"
        "       aws ssm describe-instance-information --region us-east-1\n"
    )


class TunnelProcess:
    """Wraps an aws ssm start-session child running on a stdlib PTY."""

    def __init__(self, pid: int, master_fd: int) -> None:
        self.pid = pid
        self.master_fd = master_fd
        self._buf = b""

    def read_until(self, patterns: list[str], timeout: float = 25.0) -> tuple[int, str]:
        """Read from PTY until one of the regex patterns matches or timeout."""
        import select
        deadline = time.monotonic() + timeout
        collected = b""
        compiled = [re.compile(p.encode()) for p in patterns]
        while time.monotonic() < deadline:
            remaining = deadline - time.monotonic()
            r, _, _ = select.select([self.master_fd], [], [], min(remaining, 0.5))
            if r:
                try:
                    chunk = os.read(self.master_fd, 4096)
                except OSError:
                    return -1, collected.decode(errors="replace")
                collected += chunk
                text = collected.decode(errors="replace")
                for i, pat in enumerate(compiled):
                    if pat.search(collected):
                        return i, text
            # Check if child exited
            try:
                wpid, status = os.waitpid(self.pid, os.WNOHANG)
                if wpid == self.pid:
                    return -1, collected.decode(errors="replace")
            except ChildProcessError:
                return -1, collected.decode(errors="replace")
        return -2, collected.decode(errors="replace")  # timeout

    def is_alive(self) -> bool:
        popen = getattr(self, "_popen", None)
        if popen is not None:
            return popen.poll() is None
        try:
            wpid, _ = os.waitpid(self.pid, os.WNOHANG)
            return wpid == 0
        except ChildProcessError:
            return False

    def terminate(self) -> None:
        popen = getattr(self, "_popen", None)
        leader_pid = self.pid
        if popen is not None:
            try:
                _signal_tunnel_children(leader_pid, signal.SIGTERM)
                try:
                    popen.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    _signal_tunnel_children(leader_pid, signal.SIGKILL)
                    try:
                        popen.kill()
                    except Exception:
                        pass
                    try:
                        popen.wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        pass
            except Exception:
                try:
                    _signal_tunnel_children(leader_pid, signal.SIGKILL)
                    try:
                        popen.kill()
                    except Exception:
                        pass
                except Exception:
                    pass
        else:
            _signal_tunnel_children(leader_pid, signal.SIGTERM)
            time.sleep(0.4)
            _signal_tunnel_children(leader_pid, signal.SIGKILL)
        try:
            os.close(self.master_fd)
        except OSError:
            pass


def start_tunnel(
    aws_exe: str,
    tunnel: TunnelConfig,
    target: str,
    region: str,
    profile: Optional[str] = None,
) -> "TunnelProcess":
    host = _resolve_host(tunnel.host)
    parameters = json.dumps(
        {
            "host": [host],
            "portNumber": [str(tunnel.remote_port)],
            "localPortNumber": [str(tunnel.local_port)],
        }
    )
    cmd = [aws_exe]
    if profile:
        cmd += ["--profile", profile]
    cmd += [
        "ssm", "start-session",
        "--target", target,
        "--region", region,
        "--document-name", SSM_DOCUMENT,
        "--parameters", parameters,
    ]

    # Allocate a PTY pair. The child gets the slave end as its controlling
    # terminal so session-manager-plugin stays alive and produces output.
    # Using subprocess.Popen (not os.fork) for compatibility with Anaconda Python.
    # Build a clean environment that guarantees session-manager-plugin is
    # findable by the aws CLI subprocess, regardless of the terminal's PATH.
    plugin_exe = shutil.which("session-manager-plugin")
    env = os.environ.copy()
    plugin_dirs = {
        "/usr/local/sessionmanagerplugin/bin",
        os.path.expanduser("~/.local/bin"),
        os.path.expanduser("~/bin"),
    }
    if plugin_exe:
        plugin_dirs.add(os.path.dirname(plugin_exe))
        print(f"  Plugin  : {plugin_exe}")
    existing_path = env.get("PATH", "")
    extra = ":".join(d for d in plugin_dirs if d not in existing_path)
    env["PATH"] = extra + ":" + existing_path if extra else existing_path

    master_fd, slave_fd = pty.openpty()
    # shell=False (default for list argv): list-form argv prevents shell metacharacter injection.
    # `cmd` is built entirely from validated CLI args + literal strings; no shell expansion path exists.
    proc_raw = subprocess.Popen(
        cmd,
        stdin=slave_fd,
        stdout=slave_fd,
        stderr=slave_fd,
        close_fds=True,
        start_new_session=True,
        env=env,
    )
    os.close(slave_fd)
    pid = proc_raw.pid
    proc = TunnelProcess(pid, master_fd)
    # Store raw Popen so we can wait() on it properly
    proc._popen = proc_raw  # type: ignore[attr-defined]

    ready_patterns = [
        r"SessionId:",
        r"Port \d+ opened",
        r"Waiting for connections",
        r"403",
        r"Forbidden",
        r"authentication failed",
        r"[Ee]rror",
    ]
    idx, output = proc.read_until(ready_patterns, timeout=25)
    clean = output.replace("\r\n", "\n").replace("\r", "\n")

    if idx == -1:  # EOF / exited
        proc.terminate()
        _diagnose_and_exit(tunnel.name, clean)
    if idx == -2:  # timeout
        proc.terminate()
        sys.exit(
            f"\nERROR: [{tunnel.name}] timed out waiting for SSM session.\n"
            f"Output: {clean.strip()}\n"
            "Run: aws sso login  then retry.\n"
        )
    if idx in (3, 4, 5, 6):  # error patterns
        proc.terminate()
        _diagnose_and_exit(tunnel.name, clean)

    # idx 0,1,2 — live. Drain PTY in background thread so buffer never fills.
    for line in clean.strip().splitlines():
        if line.strip():
            print(f"  {line.strip()}")
    print(f"  [{tunnel.name}] tunnel open → localhost:{tunnel.local_port}")

    def _drain() -> None:
        while proc.is_alive():
            try:
                import select
                r, _, _ = select.select([master_fd], [], [], 1.0)
                if r:
                    os.read(master_fd, 4096)
            except OSError:
                break

    threading.Thread(target=_drain, daemon=True).start()
    return proc


def terminate_all(procs: dict[str, TunnelProcess]) -> None:
    for name, proc in procs.items():
        print(f"  Stopping {name} tunnel (pid {proc.pid})...")
        proc.terminate()


def main() -> int:
    args = parse_args()

    # Validate CLI inputs before any subprocess call (Fortify "Command Injection"
    # defense-in-depth on top of shell=False list-form subprocess invocation).
    _validate_args(args)

    # Profile resolution:
    #   --profile <name>  → use exactly that name (no prompt)
    #   (nothing passed)  → interactive picker every time
    # "default" is treated as the AWS default credential chain (no --profile
    # flag forwarded to the AWS CLI) so the normal env-var chain is used.
    if args.profile is None:
        args.profile = _prompt_profile()
    if args.profile and args.profile.lower() == "default":
        args.profile = None  # don't pass --profile to the AWS CLI

    tunnels = build_tunnel_configs(args)
    if not any(t.enabled for t in tunnels):
        sys.stderr.write(
            "ERROR: no SSM port-forwards will be created — every tunnel is turned off. "
            "You must keep at least one of: backend, frontend, graph, midas_nlb, or midas_alb, "
            "or pass --with-ai-gateway or --ai-gateway-only and enable at least one Exlerate tunnel. "
            "Check your --no-* flags. Run with -h to see the full list.\n"
        )
        return 2

    # aws CLI and session-manager-plugin must be present before anything else.
    aws_exe = check_aws_cli()
    check_session_manager_plugin()

    # Midas EKS on jumpbox: only when a Midas pod tunnel may need autoresolution (skip for
    # --ai-gateway-only when all Midas tunnels are off).
    if not args.ai_gateway_only or any(
        t.enabled
        for t in tunnels
        if t.name in ("backend", "frontend", "graph")
    ):
        configure_jumpbox_kubeconfig(
            aws_exe, args.target, args.region, args.eks_cluster, args.profile,
        )

    # Auto-resolve pod IPs (MIDAS) unless --no-kubectl.
    if args.use_kubectl:
        for svc_name, label in (
            ("backend",  BACKEND_POD_LABEL),
            ("frontend", FRONTEND_POD_LABEL),
            ("graph",    GRAPH_POD_LABEL),
        ):
            tunnel = next((t for t in tunnels if t.name == svc_name), None)
            if tunnel is not None and tunnel.enabled and not tunnel.host:
                tunnel.host = resolve_pod_ip_via_ssm(
                    svc_name, label, args.namespace,
                    aws_exe, args.target, args.region, args.profile,
                )

    needs_ai_pods = (
        args.use_kubectl
        and args.with_ai_gateway
        and args.ai_kubeconfig_enabled
    )
    wants_exlerate_pods = needs_ai_pods and any(
        [
            bool(args.litellm_pod_enabled and not args.litellm_pod_host),
            bool(args.langfuse_pod_enabled and not args.langfuse_pod_host),
            bool(args.c1_pod_enabled and not args.c1_pod_host),
        ],
    )
    if wants_exlerate_pods and args.ai_eks_cluster:
        print(
            f"  ai_gateway: refreshing kubeconfig for {args.ai_eks_cluster!r} "
            "(Exlerate pod autoresolution) ...",
        )
        configure_jumpbox_kubeconfig(
            aws_exe, args.target, args.region, args.ai_eks_cluster, args.profile,
        )
    if args.use_kubectl and args.with_ai_gateway:
        for svc_name, label, ns in (
            ("litellm_pod", args.litellm_pod_label, args.litellm_namespace),
            ("langfuse_pod", args.langfuse_pod_label, args.langfuse_namespace),
            ("c1_pod", args.c1_pod_label, args.c1_namespace),
        ):
            tunnel = next((t for t in tunnels if t.name == svc_name), None)
            if tunnel is None or not tunnel.enabled or tunnel.host:
                continue
            if not needs_ai_pods:
                continue
            if not args.ai_eks_cluster:
                sys.exit(
                    "ERROR: Exlerate pod autoresolution needs --ai-eks-cluster (or set pod IPs / "
                    "use --no-ai-kubeconfig and pass --*-pod-host).\n",
                )
            tunnel.host = resolve_pod_ip_via_ssm(
                svc_name, label, ns,
                aws_exe, args.target, args.region, args.profile,
            )

    validate_tunnels(tunnels)

    # Pre-flight: verify credentials are valid before attempting any tunnels.
    sts_cmd = [aws_exe]
    if args.profile:
        sts_cmd += ["--profile", args.profile]
        os.environ["AWS_PROFILE"] = args.profile
    sts_cmd += ["sts", "get-caller-identity", "--region", args.region]

    # shell=False (default): list-form argv prevents shell metacharacter injection.
    cred_check = subprocess.run(sts_cmd, capture_output=True, text=True)
    if cred_check.returncode != 0:
        print(
            "\nERROR: AWS credentials are invalid or expired.\n"
            f"Profile: {args.profile or '(default)'}\n"
            f"Detail:  {cred_check.stderr.strip()}\n"
        )
        try:
            ans = input("Run 'aws sso login' now? [Y/n] ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            ans = "n"
        if ans not in ("n", "no"):
            login_cmd = [aws_exe, "sso", "login"]
            if args.profile:
                login_cmd += ["--profile", args.profile]
            # shell=False (default): list-form argv prevents shell metacharacter injection.
            subprocess.run(login_cmd)
            # shell=False (default): list-form argv prevents shell metacharacter injection.
            cred_check2 = subprocess.run(sts_cmd, capture_output=True, text=True)
            if cred_check2.returncode != 0:
                sys.exit(
                    "\nERROR: Still unable to authenticate after sso login.\n"
                    f"Detail: {cred_check2.stderr.strip()}\n"
                )
            cred_check = cred_check2
        else:
            sys.exit("Aborted.\n")
    identity = json.loads(cred_check.stdout)
    print(f"Identity: {identity.get('Arn','?')}\n")

    active = [t for t in tunnels if t.enabled]

    print(f"Jumpbox : {args.target}  (region: {args.region})")
    print(f"Starting {len(active)} tunnel(s):\n")

    procs: dict[str, TunnelProcess] = {}
    for tunnel in active:
        print(f"  [{tunnel.name}]  {tunnel.host}:{tunnel.remote_port} → localhost:{tunnel.local_port}  ({tunnel.description})")
        procs[tunnel.name] = start_tunnel(aws_exe, tunnel, args.target, args.region, args.profile)
        time.sleep(0.5)

    print("\n" + "─" * 60)
    print("Tunnels ready — connect at:")
    if args.with_ai_gateway and not args.ai_gateway_only:
        print("  (MIDAS and ai_gateway: each [NAME] is only active if listed above)")
    if args.with_ai_gateway and args.ai_gateway_only:
        print("  (ai_gateway only: each [NAME] is only active if listed above)")

    midas_names = {"backend", "frontend", "graph", "midas_nlb", "midas_alb"}
    for tunnel in active:
        stack = "MIDAS" if tunnel.name in midas_names else "EXLERATE"
        print(f"\n  [{stack}] [{tunnel.name.upper()}]  localhost:{tunnel.local_port}  (remote {tunnel.host}:{tunnel.remote_port})")
        for hint in tunnel.hints:
            print(hint)

    if args.with_ai_gateway:
        print_exlerate_url_reference(args)
    else:
        print(
            "\n  No Exlerate (AI Gateway) URLs: that block only appears with --with-ai-gateway, "
            "plus Exlerate load-balancer host flags or env (e.g. LITELLM_NLB_HOST, …). "
            "Without it, this run is MIDAS-only by design."
        )

    print("\n" + "─" * 60)
    print("Press Ctrl+C to stop all tunnels.\n")

    def _handle_signal(signum: int, _frame: object) -> None:
        print(f"\nReceived signal {signum} – shutting down all tunnels...")
        terminate_all(procs)
        sys.exit(0)

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    while True:
        for name in list(procs):
            if not procs[name].is_alive():
                print(f"  [{name}] tunnel exited unexpectedly")
                procs[name].terminate()
                procs.pop(name)
        if not procs:
            break
        time.sleep(1)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

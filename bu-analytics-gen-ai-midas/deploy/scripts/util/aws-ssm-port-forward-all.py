#!/usr/bin/env python3
"""Start one or more AWS SSM port-forwarding sessions to MIDAS services via a jumpbox.

Uses the AWS-StartPortForwardingSessionToRemoteHost SSM document to tunnel traffic
from local ports → SSM agent on the jumpbox → service endpoints inside the VPC.

Matches the MIDAS 443 ingress topology defined in deploy/ecs-app/alb-nlb.tf:

    Corporate / Jumpbox → NLB TCP:443 → ALB HTTPS:443 (TLS terminates)
                                      → frontend pods HTTP:8080
                                      → backend  pods HTTP:8000
                                      → graph    pods HTTP:8001

The two 443 entry points (NLB and ALB) and all three pod-direct ports are
exposed as independent tunnels. By default every tunnel is started. Use
--no-<tunnel> to suppress individual ones (e.g. --no-backend / --no-frontend /
--no-graph / --no-nlb / --no-alb).

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

Service defaults
  backend   host: auto-resolved from EKS pod (label app.kubernetes.io/name=midas-api-backend-svc)
            or BACKEND_NODE_IP env var                             remote: 8000  local: 9081
  frontend  host: auto-resolved from EKS pod (label app.kubernetes.io/name=midas-web-frontend-svc)
            or FRONTEND_NODE_IP env var                            remote: 8080  local: 9000
  graph     host: auto-resolved from EKS pod (label app.kubernetes.io/name=midas-graph-svc)
            or GRAPH_NODE_IP env var                               remote: 8001  local: 9083
  nlb       host: NLB_DNS env var (TCP 443, passes through to ALB) remote: 443   local: 9082
  alb       host: ALB_DNS env var (HTTPS 443, TLS terminates,
            path-routed to pods: /frontend /backend /graph)        remote: 443   local: 9084

Pod IP resolution (backend / frontend / graph – only when tunnel is enabled):
  When --<service>-host is not supplied and <SERVICE>_NODE_IP is not set, the script
  sends an AWS-RunShellScript SSM command to the jumpbox that runs:
    kubectl get pods -n <namespace> -l app.kubernetes.io/name=midas-<service>-svc \\
        -o jsonpath=...
  on the jumpbox (which has VPC access to the private EKS API server), then parses
  the podIP from the result.  This works from any laptop without VPN.
  Use --no-kubectl to skip auto-resolution and supply --<service>-host manually.

Usage examples:

  # All tunnels – backend/frontend/graph IPs resolved automatically from EKS:
  python3 deploy/scripts/util/aws-ssm-port-forward-all.py \\
      --nlb-host <nlb-dns>

  # Backend and NLB only (no kubectl needed for backend if --backend-host is given):
  python3 deploy/scripts/util/aws-ssm-port-forward-all.py \\
      --no-frontend --no-graph --nlb-host <nlb-dns>

  # Frontend tunnel only – pod IP auto-resolved via SSM on the jumpbox (no local kubectl needed):
  python3 deploy/scripts/util/aws-ssm-port-forward-all.py \\
      --no-backend --no-graph --no-nlb

  # Frontend tunnel only – supply pod IP explicitly (skips SSM resolution):
  python3 deploy/scripts/util/aws-ssm-port-forward-all.py \\
      --no-backend --no-graph --no-nlb --no-kubectl \\
      --frontend-host <FRONTEND_POD_IP>

  # Override the backend local port and jumpbox:
  python3 deploy/scripts/util/aws-ssm-port-forward-all.py \\
      --target i-0abc1234def56789 \\
      --backend-local-port 19081 \\
      --nlb-host <nlb-dns>

After starting, tunnels are accessible at:
  Backend  : http://localhost:9081/health         (FastAPI health, pod-direct)
             http://localhost:9081/docs           (Swagger UI)
  Frontend : http://localhost:9000/               (frontend pod direct)
  Graph    : http://localhost:9083/health         (GraphRAG health, pod-direct)
  NLB      : https://localhost:9082/frontend/     (MIDAS UI via NLB → ALB)
             https://localhost:9082/backend/health
             https://localhost:9082/graph/health
  ALB      : https://localhost:9084/frontend/     (MIDAS UI via ALB direct, bypasses NLB)
             https://localhost:9084/backend/health
             https://localhost:9084/graph/health

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


# ---------------------------------------------------------------------------
# MIDAS project defaults – override via CLI flags or env vars
# ---------------------------------------------------------------------------
DEFAULT_TARGET = "i-04231b2a8a4d98b63"
DEFAULT_REGION = "us-east-1"
DEFAULT_NAMESPACE = "midas-apps"
DEFAULT_EKS_CLUSTER = "midas-eks-dev"
SSM_DOCUMENT = "AWS-StartPortForwardingSessionToRemoteHost"

# Kubernetes label selectors – each matches the app.kubernetes.io/name label that the
# respective Helm chart stamps on every pod it manages (Chart.Name = service name).
FRONTEND_POD_LABEL = "app.kubernetes.io/name=midas-web-frontend-svc"
BACKEND_POD_LABEL  = "app.kubernetes.io/name=midas-api-backend-svc"
GRAPH_POD_LABEL    = "app.kubernetes.io/name=midas-graph-svc"

# Env-var overrides (still honoured; auto-resolve is used when these are empty).
BACKEND_NODE_IP = os.environ.get("BACKEND_NODE_IP", "")
FRONTEND_NODE_IP = os.environ.get("FRONTEND_NODE_IP", "")
GRAPH_NODE_IP = os.environ.get("GRAPH_NODE_IP", "")
NLB_DNS = os.environ.get("NLB_DNS", "")
ALB_DNS = os.environ.get("ALB_DNS", "")


@dataclass
class TunnelConfig:
    name: str
    host: str
    remote_port: int
    local_port: int
    enabled: bool = True
    description: str = ""
    hints: list[str] = field(default_factory=list)


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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Start one or more SSM port-forward tunnels to MIDAS services "
            "via a jumpbox EC2 instance. All active tunnels close together on exit."
        ),
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

    # ── NLB tunnel ───────────────────────────────────────────────────────────
    nlb = parser.add_argument_group("nlb tunnel")
    nlb.add_argument(
        "--no-nlb",
        dest="nlb_enabled",
        action="store_false",
        default=True,
        help="Disable the NLB tunnel (default: enabled)",
    )
    nlb.add_argument(
        "--nlb-host",
        default=NLB_DNS,
        metavar="DNS_NAME",
        help=(
            f"NLB DNS name (default: {NLB_DNS!r} from NLB_DNS env var). "
            "Get with: cd deploy/ecs-app && terraform output -raw nlb_dns_name"
        ),
    )
    nlb.add_argument(
        "--nlb-port",
        type=int,
        default=443,
        metavar="PORT",
        help="Remote port on the NLB (default: 443)",
    )
    nlb.add_argument(
        "--nlb-local-port",
        type=int,
        default=9082,
        metavar="LOCAL_PORT",
        help="Local port for the NLB tunnel (default: 9082)",
    )

    # ── ALB tunnel ───────────────────────────────────────────────────────────
    # The ALB is the HTTPS termination point (ACM cert on port 443). Tunneling
    # here lets you exercise the ALB path-routing rules (/frontend /backend
    # /graph) directly, bypassing the NLB pass-through layer.
    alb = parser.add_argument_group("alb tunnel")
    alb.add_argument(
        "--no-alb",
        dest="alb_enabled",
        action="store_false",
        default=True,
        help="Disable the ALB tunnel (default: enabled)",
    )
    alb.add_argument(
        "--alb-host",
        default=ALB_DNS,
        metavar="DNS_NAME",
        help=(
            f"ALB DNS name (default: {ALB_DNS!r} from ALB_DNS env var). "
            "Get with: cd deploy/ecs-app && terraform output -raw alb_dns_name"
        ),
    )
    alb.add_argument(
        "--alb-port",
        type=int,
        default=443,
        metavar="PORT",
        help="Remote port on the ALB HTTPS listener (default: 443)",
    )
    alb.add_argument(
        "--alb-local-port",
        type=int,
        default=9084,
        metavar="LOCAL_PORT",
        help="Local port for the ALB tunnel (default: 9084)",
    )

    return parser.parse_args()


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
            name="nlb",
            host=args.nlb_host,
            remote_port=args.nlb_port,
            local_port=args.nlb_local_port,
            enabled=args.nlb_enabled,
            description="NLB TCP:443 (pass-through to ALB)",
            hints=[
                f"  UI     : https://localhost:{args.nlb_local_port}/frontend/",
                f"  Backend: https://localhost:{args.nlb_local_port}/backend/health",
                f"  Graph  : https://localhost:{args.nlb_local_port}/graph/health",
            ],
        ),
        TunnelConfig(
            name="alb",
            host=args.alb_host,
            remote_port=args.alb_port,
            local_port=args.alb_local_port,
            enabled=args.alb_enabled,
            description="ALB HTTPS:443 (TLS terminates, path-routed to pods)",
            hints=[
                f"  UI     : https://localhost:{args.alb_local_port}/frontend/",
                f"  Backend: https://localhost:{args.alb_local_port}/backend/health",
                f"  Graph  : https://localhost:{args.alb_local_port}/graph/health",
            ],
        ),
    ]


def validate_tunnels(tunnels: list[TunnelConfig]) -> None:
    errors: list[str] = []
    for t in tunnels:
        if not t.enabled:
            continue
        if not t.host:
            errors.append(
                f"  {t.name}: --{t.name}-host is required (no default / env var set)"
            )
    if errors:
        sys.stderr.write("ERROR: missing host for enabled tunnel(s):\n")
        for e in errors:
            sys.stderr.write(e + "\n")
        sys.stderr.write(
            "\nDisable unneeded tunnels with --no-<name> or supply the missing --<name>-host values.\n"
        )
        sys.exit(2)

    active = [t for t in tunnels if t.enabled]
    if not active:
        sys.stderr.write("ERROR: all tunnels are disabled. Enable at least one.\n")
        sys.exit(2)


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
                    f"\n# Added by aws-ssm-port-forward-all.py\n"
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

    # aws CLI and session-manager-plugin must be present before anything else.
    aws_exe = check_aws_cli()
    check_session_manager_plugin()

    # Always refresh the kubeconfig on the jumpbox so kubectl works for any
    # subsequent SSM command – regardless of whether pod auto-resolution is
    # enabled or the user supplied hosts manually.
    configure_jumpbox_kubeconfig(
        aws_exe, args.target, args.region, args.eks_cluster, args.profile,
    )

    # Auto-resolve pod IPs for enabled tunnels whose host is not already set,
    # unless --no-kubectl was passed.  Resolution runs kubectl on the jumpbox
    # via SSM (AWS-RunShellScript) because the EKS API server is private and
    # not reachable directly from a laptop outside the VPC.
    if args.use_kubectl:
        _auto_resolve = [
            ("backend",  BACKEND_POD_LABEL),
            ("frontend", FRONTEND_POD_LABEL),
            ("graph",    GRAPH_POD_LABEL),
        ]
        for svc_name, label in _auto_resolve:
            tunnel = next((t for t in tunnels if t.name == svc_name), None)
            if tunnel is not None and tunnel.enabled and not tunnel.host:
                tunnel.host = resolve_pod_ip_via_ssm(
                    svc_name, label, args.namespace,
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
    print("Tunnels ready – connect at:")
    for tunnel in active:
        print(f"\n  [{tunnel.name.upper()}]  (localhost:{tunnel.local_port})")
        for hint in tunnel.hints:
            print(hint)

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

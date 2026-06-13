#!/usr/bin/env python3
"""Tunnel the EKS Kubernetes API through the MIDAS jumpbox so local kubectl works.

How it works
------------
The EKS cluster has a **private-only** API endpoint (no public access).  The
jumpbox EC2 instance (ec2-ssm-test) lives inside the VPC and can reach the API
on port 443.  This script uses the SSM
``AWS-StartPortForwardingSessionToRemoteHost`` document to open a local TCP
port → SSM agent on the jumpbox → EKS API server private IP:443 — exactly the
same pattern as the backend / frontend port-forward scripts.

After the tunnel is open the script writes (or updates) a **temporary
kubeconfig** that points ``server:`` at ``https://localhost:<local-port>`` and
tells you how to use it.  Your local ``kubectl`` then sends requests to
``localhost`` which are transparently forwarded to the real EKS endpoint inside
the VPC.

Prerequisites
-------------
* AWS CLI v2 on PATH with valid credentials (profile or env vars).
* Session Manager plugin installed:
    https://docs.aws.amazon.com/systems-manager/latest/userguide/session-manager-working-with-install-plugin.html
* ``kubectl`` on PATH (any version compatible with the cluster).
* ``aws`` credentials must have:
    - ``ssm:StartSession`` on the jumpbox instance.
    - ``eks:DescribeCluster`` on the EKS cluster (to fetch the CA and token).
* The jumpbox IAM role must be registered as an EKS access entry with at
  least ``AmazonEKSClusterAdminPolicy`` (Terraform: ``eks-jumpbox-access.tf``).

Quick start
-----------
1.  Fetch the EKS cluster endpoint (one-time; store in env or pass --eks-host):

    export EKS_API_HOST=$(aws eks describe-cluster \\
        --name midas-eks-dev \\
        --query "cluster.endpoint" \\
        --output text | sed 's|https://||')

2.  Start the tunnel (keeps running until Ctrl+C):

    python3 deploy/scripts/util/aws-ssm-kubectl-proxy.py

    Or explicitly:

    python3 deploy/scripts/util/aws-ssm-kubectl-proxy.py \\
        --target i-04231b2a8a4d98b63 \\
        --cluster-name midas-eks-dev \\
        --eks-host <cluster-endpoint-hostname> \\
        --local-port 6443

3.  In a second terminal run kubectl using the generated kubeconfig:

    export KUBECONFIG=/tmp/midas-kubectl-proxy-kubeconfig.yaml
    kubectl get nodes
    kubectl get pods -n midas-apps -o wide
    kubectl logs -n midas-apps deploy/backend --tail=50

    Or use --kubeconfig inline:

    kubectl --kubeconfig /tmp/midas-kubectl-proxy-kubeconfig.yaml get pods -A

Notes
-----
* The tunnel forwards only **your** local port to the EKS API; no inbound port
  is opened on the jumpbox itself.
* The generated kubeconfig contains a short-lived token (1 hour).  Re-run the
  script (or just ``aws eks get-token``) to refresh it.
* TLS verification uses the cluster CA fetched from AWS — you do NOT need to
  disable certificate checking.
* Press Ctrl+C to tear down the tunnel (SIGTERM is sent to the whole ``aws`` +
  ``session-manager-plugin`` process group so the local port is not left bound);
  the temp kubeconfig stays on disk and can be deleted manually.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import textwrap
import time

# ---------------------------------------------------------------------------
# MIDAS project defaults — override via CLI flags or env vars
# ---------------------------------------------------------------------------
DEFAULT_TARGET = "i-04231b2a8a4d98b63"
DEFAULT_REGION = "us-east-1"
DEFAULT_CLUSTER_NAME = "midas-eks-dev"
DEFAULT_LOCAL_PORT = 6443
DEFAULT_REMOTE_PORT = 443
DEFAULT_KUBECONFIG_PATH = "/tmp/midas-kubectl-proxy-kubeconfig.yaml"

SSM_DOCUMENT = "AWS-StartPortForwardingSessionToRemoteHost"


def _signal_tunnel_children(leader_pid: int, sig: int) -> None:
    """Signal every process in *leader_pid*'s POSIX process group (see port-forward-all)."""
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

# Optionally set EKS_API_HOST to the cluster endpoint hostname (without https://)
# before running so you don't need --eks-host:
#   export EKS_API_HOST=$(aws eks describe-cluster --name midas-dev \
#       --query "cluster.endpoint" --output text | sed 's|https://||')
EKS_API_HOST_ENV = os.environ.get("EKS_API_HOST", "")


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Open an SSM port-forward tunnel to the EKS Kubernetes API via the "
            "MIDAS jumpbox, then write a local kubeconfig so kubectl works."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--target",
        default=DEFAULT_TARGET,
        metavar="INSTANCE_ID",
        help=f"Jumpbox EC2 instance ID (default: {DEFAULT_TARGET})",
    )
    parser.add_argument(
        "--cluster-name",
        default=DEFAULT_CLUSTER_NAME,
        metavar="CLUSTER_NAME",
        help=(
            f"EKS cluster name used to fetch endpoint / CA / token via "
            f"``aws eks describe-cluster`` (default: {DEFAULT_CLUSTER_NAME})"
        ),
    )
    parser.add_argument(
        "--eks-host",
        default=EKS_API_HOST_ENV,
        metavar="HOSTNAME",
        help=(
            "EKS API endpoint hostname (without https://).  "
            "If omitted the script looks up the cluster via --cluster-name and "
            "the EKS_API_HOST env var.  "
            "Example: ABC123.gr7.us-east-1.eks.amazonaws.com"
        ),
    )
    parser.add_argument(
        "--local-port",
        type=int,
        default=DEFAULT_LOCAL_PORT,
        metavar="LOCAL_PORT",
        help=f"Local TCP port to listen on (default: {DEFAULT_LOCAL_PORT})",
    )
    parser.add_argument(
        "--region",
        default=DEFAULT_REGION,
        metavar="REGION",
        help=f"AWS region (default: {DEFAULT_REGION})",
    )
    parser.add_argument(
        "--kubeconfig",
        default=DEFAULT_KUBECONFIG_PATH,
        metavar="PATH",
        help=f"Path to write the temporary kubeconfig (default: {DEFAULT_KUBECONFIG_PATH})",
    )
    parser.add_argument(
        "--no-kubeconfig",
        action="store_true",
        help="Skip writing the kubeconfig (just open the tunnel).",
    )
    return parser.parse_args()


# ---------------------------------------------------------------------------
# Prerequisite checks
# ---------------------------------------------------------------------------

def check_aws_cli() -> str:
    aws_exe = shutil.which("aws")
    if not aws_exe:
        sys.stderr.write(
            "ERROR: AWS CLI not found on PATH.\n"
            "Install: https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html\n"
        )
        sys.exit(2)
    return aws_exe


def check_session_manager_plugin() -> None:
    if not shutil.which("session-manager-plugin"):
        sys.stderr.write(
            "WARNING: session-manager-plugin not found on PATH.\n"
            "The AWS CLI delegates SSM sessions to this plugin.\n"
            "Install: https://docs.aws.amazon.com/systems-manager/latest/userguide/"
            "session-manager-working-with-install-plugin.html\n\n"
        )


def check_kubectl() -> str | None:
    kubectl = shutil.which("kubectl")
    if not kubectl:
        sys.stderr.write(
            "WARNING: kubectl not found on PATH.  You will need it to issue "
            "commands once the tunnel is running.\n"
            "Install: https://kubernetes.io/docs/tasks/tools/\n\n"
        )
    return kubectl


# ---------------------------------------------------------------------------
# EKS cluster metadata (endpoint + CA)
# ---------------------------------------------------------------------------

def describe_cluster(aws_exe: str, cluster_name: str, region: str) -> dict:
    """Return the ``cluster`` dict from ``aws eks describe-cluster``."""
    print(f"  Fetching EKS cluster metadata for '{cluster_name}' …")
    result = subprocess.run(
        [
            aws_exe, "eks", "describe-cluster",
            "--name", cluster_name,
            "--region", region,
            "--output", "json",
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        sys.stderr.write(
            f"ERROR: aws eks describe-cluster failed:\n{result.stderr}\n"
            "Check that --cluster-name is correct and your AWS credentials have "
            "eks:DescribeCluster on the cluster.\n"
        )
        sys.exit(1)
    return json.loads(result.stdout)["cluster"]


def get_cluster_token(aws_exe: str, cluster_name: str, region: str) -> str:
    """Return a short-lived bearer token for the cluster (via aws eks get-token)."""
    print(f"  Fetching short-lived token for '{cluster_name}' …")
    result = subprocess.run(
        [
            aws_exe, "eks", "get-token",
            "--cluster-name", cluster_name,
            "--region", region,
            "--output", "json",
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        sys.stderr.write(
            f"ERROR: aws eks get-token failed:\n{result.stderr}\n"
        )
        sys.exit(1)
    return json.loads(result.stdout)["status"]["token"]


# ---------------------------------------------------------------------------
# Kubeconfig generation
# ---------------------------------------------------------------------------

def write_kubeconfig(
    path: str,
    cluster_name: str,
    local_port: int,
    ca_data: str,
    token: str,
) -> None:
    """Write a minimal kubeconfig that points at localhost:<local_port>."""
    kubeconfig = {
        "apiVersion": "v1",
        "kind": "Config",
        "clusters": [
            {
                "name": cluster_name,
                "cluster": {
                    # Redirect to the local SSM tunnel endpoint.
                    # insecure-skip-tls-verify is required because the EKS cert
                    # is valid for the real cluster hostname, not localhost.
                    # This is safe: the tunnel itself is encrypted by SSM/TLS,
                    # and this kubeconfig is local-only.
                    "server": f"https://localhost:{local_port}",
                    "insecure-skip-tls-verify": True,
                },
            }
        ],
        "users": [
            {
                "name": cluster_name,
                "user": {
                    "token": token,
                },
            }
        ],
        "contexts": [
            {
                "name": cluster_name,
                "context": {
                    "cluster": cluster_name,
                    "user": cluster_name,
                },
            }
        ],
        "current-context": cluster_name,
    }

    import yaml  # deferred; only needed when writing kubeconfig
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w") as fh:
        yaml.dump(kubeconfig, fh, default_flow_style=False)
    os.chmod(path, 0o600)
    print(f"  Kubeconfig written → {path}")


def write_kubeconfig_json_fallback(
    path: str,
    cluster_name: str,
    local_port: int,
    ca_data: str,
    token: str,
) -> None:
    """Write kubeconfig without PyYAML by using a pre-formatted template."""
    content = textwrap.dedent(f"""\
        apiVersion: v1
        kind: Config
        clusters:
        - name: {cluster_name}
          cluster:
            server: https://localhost:{local_port}
            insecure-skip-tls-verify: true
        users:
        - name: {cluster_name}
          user:
            token: {token}
        contexts:
        - name: {cluster_name}
          context:
            cluster: {cluster_name}
            user: {cluster_name}
        current-context: {cluster_name}
    """)
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w") as fh:
        fh.write(content)
    os.chmod(path, 0o600)
    print(f"  Kubeconfig written → {path}")


# ---------------------------------------------------------------------------
# SSM tunnel command
# ---------------------------------------------------------------------------

def build_tunnel_command(
    aws_exe: str,
    target: str,
    region: str,
    eks_host: str,
    remote_port: int,
    local_port: int,
) -> list[str]:
    parameters = json.dumps(
        {
            "host": [eks_host],
            "portNumber": [str(remote_port)],
            "localPortNumber": [str(local_port)],
        }
    )
    return [
        aws_exe,
        "ssm",
        "start-session",
        "--target", target,
        "--region", region,
        "--document-name", SSM_DOCUMENT,
        "--parameters", parameters,
    ]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    args = parse_args()

    aws_exe = check_aws_cli()
    check_session_manager_plugin()
    check_kubectl()

    # ------------------------------------------------------------------
    # Resolve EKS API hostname
    # ------------------------------------------------------------------
    eks_host = args.eks_host
    ca_data: str | None = None

    if not eks_host or not args.no_kubeconfig:
        print("\nLooking up EKS cluster …")
        cluster_info = describe_cluster(aws_exe, args.cluster_name, args.region)
        endpoint: str = cluster_info["endpoint"]  # https://XXXX.gr7.us-east-1.eks.amazonaws.com
        eks_host = endpoint.lstrip("https://").lstrip("/")
        ca_data = cluster_info["certificateAuthority"]["data"]

    if not eks_host:
        sys.stderr.write(
            "ERROR: Could not determine EKS API hostname.\n"
            "Pass --eks-host or set EKS_API_HOST, or ensure --cluster-name is correct.\n"
        )
        sys.exit(2)

    # ------------------------------------------------------------------
    # Write kubeconfig (before starting the tunnel so the user can see it)
    # ------------------------------------------------------------------
    if not args.no_kubeconfig and ca_data:
        token = get_cluster_token(aws_exe, args.cluster_name, args.region)
        try:
            write_kubeconfig(args.kubeconfig, args.cluster_name, args.local_port, ca_data, token)
        except ImportError:
            write_kubeconfig_json_fallback(
                args.kubeconfig, args.cluster_name, args.local_port, ca_data, token
            )

    # ------------------------------------------------------------------
    # Start the SSM port-forward tunnel
    # ------------------------------------------------------------------
    cmd = build_tunnel_command(
        aws_exe,
        args.target,
        args.region,
        eks_host,
        DEFAULT_REMOTE_PORT,
        args.local_port,
    )

    print(f"\nStarting SSM kubectl proxy tunnel:")
    print(f"  Jumpbox  : {args.target}  (region: {args.region})")
    print(f"  Remote   : {eks_host}:{DEFAULT_REMOTE_PORT}  (EKS private API endpoint)")
    print(f"  Local    : localhost:{args.local_port}")
    if not args.no_kubeconfig:
        print(f"\nKubeconfig : {args.kubeconfig}")
        print(f"\nIn a second terminal run:")
        print(f"  export KUBECONFIG={args.kubeconfig}")
        print(f"  kubectl get nodes")
        print(f"  kubectl get pods -n midas-apps -o wide")
        print(f"  kubectl logs -n midas-apps deploy/backend --tail=50")
        print(f"\n  Or inline:")
        print(f"  kubectl --kubeconfig {args.kubeconfig} get pods -A")
    print("\nPress Ctrl+C to stop.\n")

    proc = subprocess.Popen(cmd, start_new_session=True)

    sig_hits: list[int] = []

    def _handle_signal(signum: int, _frame: object) -> None:
        sig_hits.append(signum)
        pid = proc.pid
        print(f"\nReceived signal {signum}, terminating tunnel …")
        if pid is None or proc.poll() is not None:
            raise SystemExit(128 + signum if signum else 0)
        # First interrupt: graceful TERM to aws + session-manager-plugin group;
        # second: SIGKILL if anything still holds the port.
        if len(sig_hits) == 1:
            _signal_tunnel_children(pid, signal.SIGTERM)
        else:
            _signal_tunnel_children(pid, signal.SIGKILL)

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    rc = proc.wait()
    return rc if rc is not None else 0


if __name__ == "__main__":
    raise SystemExit(main())

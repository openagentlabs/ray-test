"""Shared deploy phases for AWS (CI-parity library). Used by make/build.py and deploy_to_aws.py."""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

_SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _SCRIPT_DIR.parents[2]
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))
if str(_REPO_ROOT / "make") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "make"))

import env_loader  # noqa: E402
from build_config import (  # noqa: E402
    AWS_ACCOUNT_ID,
    AWS_CLI_PROFILE,
    AWS_DEFAULT_REGION,
    AWS_ENV_FILE,
    COMPOSE_FILE,
    EKS_CLUSTER,
    HELM_CHART_DIR,
    K8S_NAMESPACE,
    LOCAL_IMAGES,
    LOCAL_HTTP_CHECKS,
    PORT_ARCH_DIAGRAM_AGENT,
    PORT_COLLABORATION,
    PORT_DOCUMENT_STORAGE,
    PORT_GENERAL_AI_AGENT,
    PORT_IAM,
    PORT_NOTIFICATION,
    PORT_SOLUTIONS,
    PORT_STORAGE,
    REPO_ROOT,
    TF_DIR,
    BuildProfile,
)

BUILD_DOCKER_SCRIPT = REPO_ROOT / "make/build_docker.py"

LOCAL_TCP_PORTS: list[tuple[str, int]] = [
    ("iam", PORT_IAM),
    ("solutions", PORT_SOLUTIONS),
    ("storage", PORT_STORAGE),
    ("general-ai-agent", PORT_GENERAL_AI_AGENT),
    ("notification", PORT_NOTIFICATION),
    ("collaboration", PORT_COLLABORATION),
    ("document-storage", PORT_DOCUMENT_STORAGE),
    ("arch-diagram-agent", PORT_ARCH_DIAGRAM_AGENT),
]

COMPOSE_SERVICES = [
    "iam",
    "general-ai-agent",
    "solutions",
    "storage",
    "notification",
    "collaboration",
    "document-storage",
    "arch-diagram-agent",
    "frontend",
]

ECS_SERVICE_CHECKS: list[tuple[str, str]] = []  # removed — EKS validation uses kubectl


@dataclass
class PhaseResult:
    name: str
    ok: bool
    detail: str = ""
    data: dict[str, Any] = field(default_factory=dict)


class DeployError(Exception):
    pass


def log(msg: str) -> None:
    print(msg, flush=True)


def run(
    cmd: list[str],
    *,
    cwd: Path | None = None,
    capture: bool = False,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    log(f"+ {' '.join(cmd)}")
    return subprocess.run(
        cmd,
        cwd=cwd or REPO_ROOT,
        check=True,
        text=True,
        capture_output=capture,
        env=env,
    )


def run_json(cmd: list[str], *, cwd: Path | None = None) -> Any:
    proc = run(cmd, cwd=cwd, capture=True)
    return json.loads(proc.stdout or "{}")


def terraform_var_file_args(profile: BuildProfile) -> list[str]:
    args: list[str] = []
    for path in profile.terraform_var_files():
        if not path.is_file():
            raise DeployError(f"missing var file: {path.relative_to(REPO_ROOT)}")
        args.extend(["-var-file", str(path)])
    return args


def apply_aws_process_env(profile: BuildProfile) -> None:
    """Set APP_ENV/APP_TARGET and merge canonical AWS credentials into this process."""
    os.environ["APP_ENV"] = profile.app_env
    os.environ["APP_TARGET"] = profile.app_target
    from aws_credentials import load_canonical_aws_env, sync_aws_cli_profile  # noqa: PLC0415

    env = load_canonical_aws_env()
    for key, value in env.items():
        if value:
            os.environ[key] = value
    sync_aws_cli_profile(env)


def phase_configure_aws(profile: BuildProfile) -> PhaseResult:
    """Verify AWS credentials, var-files, and EKS deploy flags before any cloud work."""
    errors: list[str] = []
    if not AWS_ENV_FILE.is_file():
        errors.append(
            f"missing {AWS_ENV_FILE.relative_to(REPO_ROOT)} — "
            "copy infra/envs/dev/.env.aws.example and set keys",
        )
    for path in profile.terraform_var_files():
        if not path.is_file():
            errors.append(f"missing {path.relative_to(REPO_ROOT)}")
    tfvars = profile.env_dir / "terraform.tfvars"
    if tfvars.is_file():
        body = tfvars.read_text(encoding="utf-8")
        if "containers_eks_enabled" not in body:
            errors.append(
                f"{tfvars.relative_to(REPO_ROOT)}: set containers_eks_enabled = true for AWS app deploy",
            )
        elif "containers_eks_enabled=true" not in body.replace(" ", ""):
            errors.append(
                f"{tfvars.relative_to(REPO_ROOT)}: containers_eks_enabled must be true for AWS app deploy",
            )
    if errors:
        return PhaseResult("configure_aws", False, "; ".join(errors))

    try:
        apply_aws_process_env(profile)
    except (ImportError, ValueError, RuntimeError) as exc:
        return PhaseResult("configure_aws", False, f"AWS env: {exc}")

    try:
        from aws_credentials import load_canonical_aws_env, verify_sts  # noqa: PLC0415

        identity = verify_sts(load_canonical_aws_env())
    except (ImportError, ValueError, RuntimeError) as exc:
        return PhaseResult("configure_aws", False, f"STS: {exc}")

    account = str(identity.get("Account", ""))
    return PhaseResult(
        "configure_aws",
        True,
        f"APP_ENV={profile.app_env} APP_TARGET=aws account={account}",
    )


def phase_scaffold_secrets(profile: BuildProfile) -> PhaseResult:
    try:
        from scaffold_secrets import scaffold_secrets  # noqa: PLC0415

        path = scaffold_secrets(profile)
        return PhaseResult(
            "scaffold_secrets",
            True,
            f"wrote {path.relative_to(REPO_ROOT)}",
        )
    except SystemExit as exc:
        return PhaseResult("scaffold_secrets", False, str(exc) or "scaffold_secrets failed")


def phase_preflight() -> PhaseResult:
    errors: list[str] = []
    version_cmds: dict[str, list[str]] = {
        "docker": ["docker", "--version"],
        "terraform": ["terraform", "--version"],
        "aws": ["aws", "--version"],
        "kubectl": ["kubectl", "version", "--client"],
        "helm": ["helm", "version", "--short"],
    }
    for tool, cmd in version_cmds.items():
        try:
            run(cmd, capture=True)
        except (subprocess.CalledProcessError, FileNotFoundError) as exc:
            errors.append(f"{tool}: {exc}")
    try:
        compose_ver = run(["docker", "compose", "version", "--short"], capture=True).stdout.strip()
        if not compose_ver:
            errors.append("docker compose: no version output")
    except subprocess.CalledProcessError as exc:
        errors.append(f"docker compose: {exc}")
    try:
        identity = run_json(
            [
                "aws",
                "sts",
                "get-caller-identity",
                "--profile",
                AWS_CLI_PROFILE,
                "--region",
                AWS_DEFAULT_REGION,
                "--output",
                "json",
            ],
        )
        if identity.get("Account") != AWS_ACCOUNT_ID:
            errors.append(
                f"AWS account mismatch: got {identity.get('Account')}, expected {AWS_ACCOUNT_ID}",
            )
    except subprocess.CalledProcessError as exc:
        errors.append(f"aws sts get-caller-identity: {exc}")
    if errors:
        return PhaseResult("preflight", False, "; ".join(errors))
    return PhaseResult("preflight", True, "docker, terraform, aws, kubectl, helm, compose OK")


def phase_validate_secrets(profile: BuildProfile) -> PhaseResult:
    secrets_path = profile.env_dir / "secrets.auto.tfvars"
    if not secrets_path.is_file():
        return PhaseResult(
            "validate_secrets",
            False,
            f"missing {secrets_path.relative_to(REPO_ROOT)} — run: "
            f"python3 make/scaffold_secrets.py {profile.app_env}",
        )
    env, created = env_loader.load_secret_workloads(region=AWS_DEFAULT_REGION)
    errors = env_loader.validate_secret_workloads(
        env,
        app_env=profile.app_env,
        app_target=profile.app_target,
    )
    if errors:
        return PhaseResult("validate_secrets", False, "; ".join(errors))
    detail = f"OK ({secrets_path.relative_to(REPO_ROOT)})"
    if created:
        detail += "; generated AUTH_SECRET in infra/local-docker-compose/.env.local — re-run scaffold_secrets"
    return PhaseResult("validate_secrets", True, detail)


def phase_terraform(
    profile: BuildProfile,
    *,
    auto_approve: bool,
    image_tag: str,
) -> PhaseResult:
    run(["terraform", "init", "-input=false"], cwd=TF_DIR)
    run(["terraform", "fmt"], cwd=TF_DIR)
    validate = subprocess.run(
        ["terraform", "validate"],
        cwd=TF_DIR,
        text=True,
        capture_output=True,
    )
    if validate.returncode != 0:
        return PhaseResult("terraform", False, validate.stderr or validate.stdout)

    var_args = terraform_var_file_args(profile)
    plan_cmd = [
        "terraform",
        "plan",
        "-input=false",
        *var_args,
        "-var",
        f"containers_image_tag={image_tag}",
        "-out=tfplan",
    ]
    run(plan_cmd, cwd=TF_DIR)

    apply_cmd = ["terraform", "apply", "-input=false", *var_args, "-var", f"containers_image_tag={image_tag}"]
    if auto_approve:
        apply_cmd.append("-auto-approve")
    else:
        apply_cmd.append("tfplan")
    run(apply_cmd, cwd=TF_DIR)

    outputs = run_json(["terraform", "output", "-json"], cwd=TF_DIR)
    ecr_urls = outputs.get("containers_ecr_repository_urls", {}).get("value") or {}
    if not ecr_urls:
        return PhaseResult(
            "terraform",
            False,
            "containers_ecr_repository_urls empty — set containers_eks_enabled in env terraform.tfvars",
        )
    return PhaseResult(
        "terraform",
        True,
        f"applied APP_ENV={profile.app_env}; {len(ecr_urls)} ECR repos",
        data={"ecr_urls": ecr_urls, "outputs": outputs},
    )


def phase_build_images(*, no_cache: bool) -> PhaseResult:
    cmd = [sys.executable, str(BUILD_DOCKER_SCRIPT)]
    if no_cache:
        cmd.append("--no-cache")
    run(cmd)
    missing = [tag for tag in LOCAL_IMAGES.values() if docker_image_missing(tag)]
    if missing:
        return PhaseResult("build_images", False, f"missing images: {', '.join(missing)}")
    return PhaseResult("build_images", True, f"built {len(LOCAL_IMAGES)} images")


def docker_image_missing(ref: str) -> bool:
    proc = subprocess.run(
        ["docker", "image", "inspect", ref],
        capture_output=True,
        text=True,
    )
    return proc.returncode != 0


def _parse_compose_env(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    return env_loader.parse_dotenv(path)


def phase_local_validate(
    profile: BuildProfile,
    *,
    compose_timeout_s: int,
) -> PhaseResult:
    compose_env = _parse_compose_env(profile.compose_env_file())
    env = {**compose_env, "APP_ENV": profile.app_env, "APP_TARGET": "local"}
    run(
        ["docker", "compose", "-f", str(COMPOSE_FILE), "up", "-d", "--remove-orphans"],
        env={**os.environ, **{k: str(v) for k, v in env.items()}},
    )

    deadline = time.monotonic() + compose_timeout_s
    unhealthy: list[str] = []
    while time.monotonic() < deadline:
        unhealthy = _unhealthy_compose_services()
        if not unhealthy:
            break
        time.sleep(5)
    if unhealthy:
        _compose_logs_tail()
        return PhaseResult(
            "local_validate",
            False,
            f"compose not healthy within {compose_timeout_s}s: {', '.join(unhealthy)}",
        )

    http_errors = [f"{n} {u}" for n, u in LOCAL_HTTP_CHECKS if not http_ok(u)]
    if http_errors:
        return PhaseResult("local_validate", False, f"HTTP failed: {', '.join(http_errors)}")

    tcp_errors = [f"{n}:{p}" for n, p in LOCAL_TCP_PORTS if not tcp_open("127.0.0.1", p)]
    if tcp_errors:
        return PhaseResult("local_validate", False, f"TCP failed: {', '.join(tcp_errors)}")

    return PhaseResult("local_validate", True, f"compose OK (APP_ENV={profile.app_env})")


def _unhealthy_compose_services() -> list[str]:
    bad: list[str] = []
    for svc in COMPOSE_SERVICES:
        proc = subprocess.run(
            ["docker", "compose", "-f", str(COMPOSE_FILE), "ps", "--format", "json", svc],
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            bad.append(svc)
            continue
        lines = [ln for ln in (proc.stdout or "").splitlines() if ln.strip()]
        if not lines:
            bad.append(svc)
            continue
        try:
            row = json.loads(lines[-1])
        except json.JSONDecodeError:
            bad.append(svc)
            continue
        state = (row.get("State") or row.get("Status") or "").lower()
        health = (row.get("Health") or "").lower()
        if "running" not in state:
            bad.append(svc)
        elif health and health not in ("healthy", ""):
            bad.append(svc)
    return bad


def _compose_logs_tail(lines: int = 40) -> None:
    log("--- compose logs (tail) ---")
    subprocess.run(
        ["docker", "compose", "-f", str(COMPOSE_FILE), "logs", "--tail", str(lines)],
        cwd=REPO_ROOT,
    )


def http_ok(url: str, timeout_s: float = 10.0) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout_s) as resp:
            return 200 <= resp.status < 500
    except (urllib.error.URLError, TimeoutError):
        return False


def tcp_open(host: str, port: int, timeout_s: float = 3.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout_s):
            return True
    except OSError:
        return False


def phase_ecr_push(ecr_urls: dict[str, str], image_tag: str) -> PhaseResult:
    registry = f"{AWS_ACCOUNT_ID}.dkr.ecr.{AWS_DEFAULT_REGION}.amazonaws.com"
    login_pw = run(
        [
            "aws",
            "ecr",
            "get-login-password",
            "--profile",
            AWS_CLI_PROFILE,
            "--region",
            AWS_DEFAULT_REGION,
        ],
        capture=True,
    ).stdout.strip()
    subprocess.run(
        ["docker", "login", "--username", "AWS", "--password-stdin", registry],
        input=login_pw,
        text=True,
        check=True,
    )
    pushed: list[str] = []
    skipped: list[str] = []
    for workload_key, local_ref in LOCAL_IMAGES.items():
        repo_url = ecr_urls.get(workload_key)
        if not repo_url:
            skipped.append(workload_key)
            continue
        remote = f"{repo_url}:{image_tag}"
        run(["docker", "tag", local_ref, remote])
        run(["docker", "push", remote])
        pushed.append(remote)
    if not pushed:
        return PhaseResult(
            "ecr_push",
            False,
            "no images pushed — run terraform apply first or enable workloads in containers_stack",
        )
    detail = f"pushed {len(pushed)} images ({image_tag})"
    if skipped:
        detail += f"; skipped {len(skipped)} (no ECR repo in terraform output)"
    return PhaseResult("ecr_push", True, detail)


def _update_kubeconfig() -> None:
    run(
        [
            "aws",
            "eks",
            "update-kubeconfig",
            "--name",
            EKS_CLUSTER,
            "--profile",
            AWS_CLI_PROFILE,
            "--region",
            AWS_DEFAULT_REGION,
        ],
        capture=True,
    )


def _helm_shared_mount_args(spec: dict[str, Any]) -> list[str]:
    args: list[str] = []
    if spec.get("lustre_mount_enabled"):
        args.extend(
            [
                "--set",
                "lustre.enabled=true",
                "--set",
                f"lustre.volumeName={spec.get('lustre_volume_name', 'shared-lustre')}",
                "--set",
                f"lustre.mountPath={spec.get('lustre_mount_path', '/mnt/lustre')}",
            ],
        )
    if spec.get("s3_shared_mount_enabled"):
        args.extend(
            [
                "--set",
                "s3SharedFiles.enabled=true",
                "--set",
                f"s3SharedFiles.volumeName={spec.get('s3_shared_volume_name', 'shared-s3-files')}",
                "--set",
                f"s3SharedFiles.mountPath={spec.get('s3_shared_mount_path', '/mnt/s3-files')}",
            ],
        )
    if spec.get("lustre_mount_enabled") or spec.get("s3_shared_mount_enabled"):
        args.extend(
            [
                "--set",
                "probes.mountHealthEnabled=true",
                "--set",
                "probes.mountHealthPath=/api/health/mounts",
                "--set",
                "sharedMounts.fsGroup=1000",
                "--set",
                "sharedMounts.runAsUser=1000",
                "--set",
                "sharedMounts.runAsGroup=1000",
                "--set",
                "sharedMounts.initWaitEnabled=true",
                "--set",
                "sharedMounts.initWaitMaxSeconds=600",
            ],
        )
    if spec.get("schedule_on_ray_nodes"):
        label_key = str(spec.get("ray_node_pool_label_key", "ray.io/node-pool"))
        label_value = str(spec.get("ray_node_pool_label_value", "ray"))
        escaped_key = label_key.replace(".", "\\.")
        args.extend(["--set", f"compute.nodeSelector.{escaped_key}={label_value}"])
    return args


def _helm_env_args(env_map: dict[str, str]) -> list[str]:
    eks_irsa_env_drop = frozenset(
        {
            "AWS_ACCESS_KEY_ID",
            "AWS_SECRET_ACCESS_KEY",
            "AWS_PROFILE",
            "AWS_DEFAULT_PROFILE",
        }
    )
    args: list[str] = []
    for key, value in sorted(env_map.items()):
        if key in eks_irsa_env_drop:
            continue
        args.extend(["--set", f"env.{key}={value}"])
    return args


def phase_helm_rollout(
    outputs: dict[str, Any],
    *,
    stable_timeout_s: int,
    workload_keys: list[str] | None = None,
) -> PhaseResult:
    deploy_specs = (
        outputs.get("containers_workload_deploy_specs", {}).get("value") or {}
    )
    if not deploy_specs:
        return PhaseResult("helm_rollout", False, "missing containers_workload_deploy_specs terraform output")

    keys = workload_keys or sorted(deploy_specs.keys())
    namespace = (outputs.get("containers_k8s_namespace", {}).get("value") or K8S_NAMESPACE).strip()
    if not namespace:
        namespace = K8S_NAMESPACE

    try:
        _update_kubeconfig()
    except subprocess.CalledProcessError as exc:
        return PhaseResult("helm_rollout", False, f"kubeconfig: exit {exc.returncode}")

    if not HELM_CHART_DIR.is_dir():
        return PhaseResult("helm_rollout", False, f"missing Helm chart at {HELM_CHART_DIR.relative_to(REPO_ROOT)}")

    released: list[str] = []
    for workload_key in keys:
        spec = deploy_specs.get(workload_key)
        if not spec:
            continue
        release = spec.get("k8s_service_name") or workload_key.replace("_", "-")
        image = spec.get("image") or ""
        if not image or ":" not in image:
            return PhaseResult("helm_rollout", False, f"{workload_key}: invalid image {image!r}")
        repo, tag = image.rsplit(":", 1)
        role_arn = spec.get("task_role_arn") or ""
        sa_annotations = (
            f"serviceAccount.annotations.eks\\.amazonaws\\.com/role-arn={role_arn}"
            if role_arn
            else ""
        )
        cmd = [
            "helm",
            "upgrade",
            "--install",
            release,
            str(HELM_CHART_DIR),
            "--namespace",
            namespace,
            "--create-namespace",
            "--set",
            f"fullnameOverride={release}",
            "--set",
            f"nameOverride={release}",
            "--set",
            f"serviceAccount.name={spec.get('service_account_name', release)}",
            "--set",
            f"image.repository={repo}",
            "--set",
            f"image.tag={tag}",
            "--set",
            f"service.port={spec.get('container_port', 8080)}",
            "--set",
            f"service.exposeLoadBalancer={'true' if spec.get('expose_load_balancer') else 'false'}",
            "--set",
            f"resources.requests.cpu={spec.get('cpu', '256m')}",
            "--set",
            f"resources.requests.memory={spec.get('memory', '512Mi')}",
            "--set",
            f"resources.limits.cpu={spec.get('cpu', '256m')}",
            "--set",
            f"resources.limits.memory={spec.get('memory', '512Mi')}",
        ]
        if sa_annotations:
            cmd.extend(["--set", sa_annotations])
        cmd.extend(_helm_shared_mount_args(spec))
        cmd.extend(_helm_env_args(spec.get("environment") or {}))
        run(cmd)
        released.append(release)

    if not released:
        return PhaseResult("helm_rollout", False, "no Helm releases upgraded")
    return PhaseResult("helm_rollout", True, f"{len(released)} releases upgraded in {namespace}")


def _manager_web_load_balancer_host(namespace: str) -> str:
    """Resolve public hostname from ALB Ingress (preferred) or legacy Service LoadBalancer."""
    for resource, name in (("ingress", "manager-web"), ("svc", "manager-web")):
        proc = run(
            [
                "kubectl",
                "get",
                resource,
                name,
                "-n",
                namespace,
                "-o",
                "jsonpath={.status.loadBalancer.ingress[0].hostname}",
            ],
            capture=True,
        )
        host = (proc.stdout or "").strip()
        if host:
            return host
    return ""


def _pods_not_ready(namespace: str, releases: list[str]) -> list[str]:
    bad: list[str] = []
    for release in releases:
        proc = subprocess.run(
            [
                "kubectl",
                "get",
                "pods",
                "-n",
                namespace,
                "-l",
                f"app.kubernetes.io/instance={release}",
                "-o",
                "jsonpath={.items[*].status.phase}",
            ],
            capture_output=True,
            text=True,
        )
        phases = [p for p in (proc.stdout or "").split() if p]
        if not phases or any(p != "Running" for p in phases):
            bad.append(release)
    return bad


def phase_validate_curl(outputs: dict[str, Any]) -> PhaseResult:
    namespace = (outputs.get("containers_k8s_namespace", {}).get("value") or K8S_NAMESPACE).strip()
    deploy_specs = outputs.get("containers_workload_deploy_specs", {}).get("value") or {}
    releases = [
        (spec.get("k8s_service_name") or key.replace("_", "-"))
        for key, spec in deploy_specs.items()
    ]

    lb_host = _manager_web_load_balancer_host(namespace)
    if not lb_host:
        return PhaseResult("validate_curl", False, "manager-web LoadBalancer hostname not ready")

    curl_errors: list[str] = []
    for label, url in [("manager-web /", f"http://{lb_host}/")]:
        ok, detail = curl_check(url)
        log(f"  curl {label}: {'OK' if ok else 'FAIL'} — {detail}")
        if not ok:
            curl_errors.append(f"{label}: {detail}")

    pod_errors = _pods_not_ready(namespace, releases)
    for release in releases:
        if release in pod_errors:
            log(f"  pod {release}: not Running")

    if curl_errors or pod_errors:
        parts = []
        if curl_errors:
            parts.append("curl: " + "; ".join(curl_errors))
        if pod_errors:
            parts.append("pods: " + ", ".join(pod_errors))
        return PhaseResult("validate_curl", False, " | ".join(parts))

    return PhaseResult(
        "validate_curl",
        True,
        f"LoadBalancer OK; {len(releases)} workloads running",
        data={"manager_web_url": f"http://{lb_host}/"},
    )


def curl_check(url: str, timeout_s: float = 15.0) -> tuple[bool, str]:
    proc = subprocess.run(
        [
            "curl",
            "-sfL",
            "--max-time",
            str(int(timeout_s)),
            "-o",
            "/dev/null",
            "-w",
            "%{http_code}",
            url,
        ],
        capture_output=True,
        text=True,
    )
    code = (proc.stdout or "").strip() or "000"
    if proc.returncode == 0 and code.startswith(("2", "3")):
        return True, f"HTTP {code}"
    return False, f"exit {proc.returncode} HTTP {code}"


def phase_aws_validate(outputs: dict[str, Any], *, alb_timeout_s: int) -> PhaseResult:
    namespace = (outputs.get("containers_k8s_namespace", {}).get("value") or K8S_NAMESPACE).strip()
    deadline = time.monotonic() + alb_timeout_s
    while time.monotonic() < deadline:
        lb_host = _manager_web_load_balancer_host(namespace)
        if lb_host:
            url = f"http://{lb_host}/"
            if http_ok(url, timeout_s=15.0):
                curl_result = phase_validate_curl(outputs)
                if not curl_result.ok:
                    return PhaseResult("aws_validate", False, curl_result.detail)
                return PhaseResult("aws_validate", True, f"manager-web at {url}", data={"manager_web_url": url})
        time.sleep(15)
    return PhaseResult("aws_validate", False, f"manager-web not reachable within {alb_timeout_s}s")


def print_summary(results: list[PhaseResult]) -> None:
    log("\n=== Deploy summary ===")
    for r in results:
        log(f"  [{'OK' if r.ok else 'FAIL'}] {r.name}: {r.detail}")
    if all(r.ok for r in results):
        url = next((r.data.get("manager_web_url") for r in results if r.data.get("manager_web_url")), None)
        if url:
            log(f"\nManager web URL: {url}")


def _default_image_tag(image_tag: str) -> str:
    if image_tag.strip():
        return image_tag.strip()
    from datetime import datetime, timezone  # noqa: PLC0415

    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")


def run_full_aws_deploy(
    profile: BuildProfile,
    *,
    auto_approve: bool = False,
    image_tag: str = "",
    no_cache: bool = False,
    skip_build: bool = False,
    skip_scaffold: bool = False,
    helm_stable_timeout: int = 900,
    alb_timeout: int = 600,
) -> int:
    """Full AWS deploy: configure → secrets → terraform → build → ECR → Helm → validate.

    Workloads run on **EKS Fargate** via the shared Helm chart under ``infra/deployed/.../helm/workload``.
    """
    tag = _default_image_tag(image_tag)
    tf_outputs: dict[str, Any] = {}
    ecr_urls: dict[str, str] = {}

    def _terraform_phase() -> PhaseResult:
        result = phase_terraform(profile, auto_approve=auto_approve, image_tag=tag)
        nonlocal tf_outputs, ecr_urls
        tf_outputs = result.data.get("outputs", {})
        ecr_urls = result.data.get("ecr_urls", {})
        return result

    phases: list[tuple[str, Callable[[], PhaseResult]]] = [
        ("configure_aws", lambda: phase_configure_aws(profile)),
        ("preflight", phase_preflight),
    ]
    if not skip_scaffold:
        phases.append(("scaffold_secrets", lambda: phase_scaffold_secrets(profile)))
    phases.extend(
        [
            ("validate_secrets", lambda: phase_validate_secrets(profile)),
            ("terraform", _terraform_phase),
        ],
    )
    if not skip_build:
        phases.append(("build_images", lambda: phase_build_images(no_cache=no_cache)))
    phases.extend(
        [
            ("ecr_push", lambda: phase_ecr_push(ecr_urls, tag)),
            (
                "helm_rollout",
                lambda: phase_helm_rollout(
                    tf_outputs,
                    stable_timeout_s=helm_stable_timeout,
                    workload_keys=sorted(ecr_urls.keys()),
                ),
            ),
            ("aws_validate", lambda: phase_aws_validate(tf_outputs, alb_timeout_s=alb_timeout)),
        ],
    )
    _, code = run_phases(phases)
    return code


def run_push_app_aws(
    profile: BuildProfile,
    *,
    image_tag: str = "",
    no_cache: bool = False,
    skip_build: bool = False,
) -> int:
    """Build service Docker images and push to ECR (requires terraform apply for repos)."""
    tag = _default_image_tag(image_tag)

    try:
        tf_outputs = run_json(["terraform", "output", "-json"], cwd=TF_DIR)
    except subprocess.CalledProcessError as exc:
        log(f"terraform output failed (exit {exc.returncode}) — run make start-aws first")
        return 1

    ecr_urls = tf_outputs.get("containers_ecr_repository_urls", {}).get("value") or {}
    if not ecr_urls:
        log("No ECR repository URLs in terraform output — run make start-aws (terraform phase) first.")
        return 1

    phases: list[tuple[str, Callable[[], PhaseResult]]] = [
        ("configure_aws", lambda: phase_configure_aws(profile)),
        ("preflight", phase_preflight),
    ]
    if not skip_build:
        phases.append(("build_images", lambda: phase_build_images(no_cache=no_cache)))
    phases.append(("ecr_push", lambda: phase_ecr_push(ecr_urls, tag)))
    _, code = run_phases(phases)
    return code


def run_phases(
    phases: list[tuple[str, Callable[[], PhaseResult]]],
) -> tuple[list[PhaseResult], int]:
    results: list[PhaseResult] = []
    try:
        for name, fn in phases:
            log(f"\n--- Phase: {name} ---")
            try:
                result = fn()
            except subprocess.CalledProcessError as exc:
                result = PhaseResult(name, False, f"command failed (exit {exc.returncode})")
            except DeployError as exc:
                result = PhaseResult(name, False, str(exc))
            results.append(result)
            if not result.ok:
                raise DeployError(result.detail or name)
    except DeployError:
        print_summary(results)
        return results, 1
    print_summary(results)
    return results, 0 if all(r.ok for r in results) else 1

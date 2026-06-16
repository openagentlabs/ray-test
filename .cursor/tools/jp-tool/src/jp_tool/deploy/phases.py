"""Deploy phase functions — each returns ``JpResult[PhaseOutcome]``."""

from __future__ import annotations

import os
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from jp_tool.core.config import AppConfig
from jp_tool.core.errors import AppError, ErrorCodes
from jp_tool.core.option import Option
from jp_tool.core.results import Failure, Success
from jp_tool.core.subprocess_runner import (
    run_command,
    run_command_checked,
    run_json_command,
)
from jp_tool.core.types import JpResult
from jp_tool.deploy.models import PhaseOutcome

LOCAL_IMAGES: dict[str, str] = {
    "frontend": "arb-frontend:local",
    "manager_web": "arb-manager-web:local",
    "iam_svc": "arb-iam-svc:local",
    "solutions_svc": "arb-solutions-svc:local",
    "storage_svc": "arb-storage-svc:local",
    "general_ai_agent_svc": "arb-general-ai-agent-svc:local",
    "notification_svc": "arb-notification-svc:local",
    "collaboration_svc": "arb-collaboration-svc:local",
    "document_storage_svc": "arb-document-storage-svc:local",
    "arch_diagram_agent_svc": "arb-arch-diagram-agent-svc:local",
}


def default_image_tag(configured: Option[str]) -> str:
    if configured and configured.strip():
        return configured.strip()
    return datetime.now(UTC).strftime("%Y%m%d-%H%M%S")


def apply_process_env(config: AppConfig) -> None:
    """Mirror legacy deploy env for child processes."""
    os.environ["APP_ENV"] = config.app.Env
    os.environ["APP_TARGET"] = config.app.Target
    os.environ["AWS_PROFILE"] = config.aws.Profile
    os.environ["AWS_DEFAULT_REGION"] = config.aws.Region


def terraform_var_file_args(config: AppConfig) -> JpResult[list[str]]:
    args: list[str] = []
    for path in config.terraform_var_files():
        if not path.is_file():
            return Failure(
                AppError(
                    code=ErrorCodes.CONFIG,
                    message="Missing Terraform var file.",
                    detail=str(path.relative_to(config.repo_root)),
                ),
            )
        args.extend(["-var-file", str(path)])
    return Success(args)


def phase_configure_aws(config: AppConfig) -> JpResult[PhaseOutcome]:
    tfvars = config.env_dir / "terraform.tfvars"
    if not tfvars.is_file():
        return Failure(
            AppError(
                code=ErrorCodes.CONFIG,
                message="Environment terraform.tfvars not found.",
                detail=str(tfvars.relative_to(config.repo_root)),
            ),
        )

    body = tfvars.read_text(encoding="utf-8")
    compact = body.replace(" ", "")
    if "containers_eks_enabled" not in body:
        return Failure(
            AppError(
                code=ErrorCodes.CONFIG,
                message="EKS deploy flag missing.",
                detail=(
                    f"{tfvars.relative_to(config.repo_root)}: set containers_eks_enabled = true"
                ),
            ),
        )
    if "containers_eks_enabled=true" not in compact:
        return Failure(
            AppError(
                code=ErrorCodes.CONFIG,
                message="EKS deploy flag disabled.",
                detail=(
                    f"{tfvars.relative_to(config.repo_root)}: containers_eks_enabled must be true"
                ),
            ),
        )

    apply_process_env(config)
    identity = run_json_command(
        [
            "aws",
            "sts",
            "get-caller-identity",
            "--profile",
            config.aws.Profile,
            "--region",
            config.aws.Region,
            "--output",
            "json",
        ],
        cwd=config.repo_root,
    )
    if isinstance(identity, Failure):
        return identity

    account = str(identity.unwrap().get("Account", ""))
    if account != config.aws.AccountId:
        return Failure(
            AppError(
                code=ErrorCodes.PREFLIGHT,
                message="AWS account mismatch.",
                detail=f"expected {config.aws.AccountId}, got {account}",
            ),
        )

    return Success(
        PhaseOutcome(
            name="configure_aws",
            ok=True,
            detail=(f"APP_ENV={config.app.Env} APP_TARGET={config.app.Target} account={account}"),
        ),
    )


def phase_preflight(config: AppConfig) -> JpResult[PhaseOutcome]:
    tools = {
        "docker": ["docker", "--version"],
        "terraform": ["terraform", "--version"],
        "aws": ["aws", "--version"],
        "kubectl": ["kubectl", "version", "--client"],
        "helm": ["helm", "version", "--short"],
    }
    errors: list[str] = []
    for tool, cmd in tools.items():
        result = run_command_checked(cmd, cwd=config.repo_root)
        if isinstance(result, Failure):
            errors.append(f"{tool}: {result.failure().detail}")

    compose = run_command_checked(
        ["docker", "compose", "version", "--short"],
        cwd=config.repo_root,
    )
    if isinstance(compose, Failure):
        errors.append(f"docker compose: {compose.failure().detail}")

    if errors:
        return Success(
            PhaseOutcome(
                name="preflight",
                ok=False,
                detail="; ".join(errors),
            ),
        )
    return Success(
        PhaseOutcome(
            name="preflight",
            ok=True,
            detail="docker, terraform, aws, kubectl, helm, compose OK",
        ),
    )


def phase_validate_secrets(config: AppConfig) -> JpResult[PhaseOutcome]:
    secrets_path = config.env_dir / "secrets.auto.tfvars"
    if not secrets_path.is_file():
        return Success(
            PhaseOutcome(
                name="validate_secrets",
                ok=False,
                detail=(
                    f"missing {secrets_path.relative_to(config.repo_root)} — "
                    f"create secrets or set Deploy.SkipScaffold=true"
                ),
            ),
        )
    return Success(
        PhaseOutcome(
            name="validate_secrets",
            ok=True,
            detail=f"OK ({secrets_path.relative_to(config.repo_root)})",
        ),
    )


def phase_terraform(
    config: AppConfig,
    *,
    auto_approve: bool,
    image_tag: str,
) -> JpResult[PhaseOutcome]:
    tf_dir = config.terraform_dir
    init = run_command_checked(["terraform", "init", "-input=false"], cwd=tf_dir)
    if isinstance(init, Failure):
        return init

    fmt = run_command_checked(["terraform", "fmt"], cwd=tf_dir)
    if isinstance(fmt, Failure):
        return fmt

    validate = run_command(["terraform", "validate"], cwd=tf_dir)
    if isinstance(validate, Failure):
        return validate
    if validate.unwrap().returncode != 0:
        proc = validate.unwrap()
        return Success(
            PhaseOutcome(
                name="terraform",
                ok=False,
                detail=proc.stderr.strip() or proc.stdout.strip(),
            ),
        )

    var_args_result = terraform_var_file_args(config)
    if isinstance(var_args_result, Failure):
        return var_args_result
    var_args = var_args_result.unwrap()

    plan_cmd = [
        "terraform",
        "plan",
        "-input=false",
        *var_args,
        "-var",
        f"containers_image_tag={image_tag}",
        "-out=tfplan",
    ]
    plan = run_command_checked(plan_cmd, cwd=tf_dir)
    if isinstance(plan, Failure):
        return plan

    apply_cmd = [
        "terraform",
        "apply",
        "-input=false",
        *var_args,
        "-var",
        f"containers_image_tag={image_tag}",
    ]
    if auto_approve:
        apply_cmd.append("-auto-approve")
    else:
        apply_cmd.append("tfplan")
    applied = run_command_checked(apply_cmd, cwd=tf_dir)
    if isinstance(applied, Failure):
        return applied

    outputs = run_json_command(["terraform", "output", "-json"], cwd=tf_dir)
    if isinstance(outputs, Failure):
        return outputs

    payload = outputs.unwrap()
    ecr_urls = payload.get("containers_ecr_repository_urls", {}).get("value") or {}
    if not ecr_urls:
        return Success(
            PhaseOutcome(
                name="terraform",
                ok=False,
                detail=("containers_ecr_repository_urls empty — enable containers_eks_enabled"),
            ),
        )

    return Success(
        PhaseOutcome(
            name="terraform",
            ok=True,
            detail=f"applied APP_ENV={config.app.Env}; {len(ecr_urls)} ECR repos",
            data={"ecr_urls": ecr_urls, "outputs": payload},
        ),
    )


def docker_image_missing(ref: str, *, cwd: Path) -> bool:
    proc = run_command(["docker", "image", "inspect", ref], cwd=cwd)
    if isinstance(proc, Failure):
        return True
    return proc.unwrap().returncode != 0


def _repo_docker_build_specs(repo_root: Path) -> dict[str, list[str]]:
    """Local image tags present in this repo that can be built with docker."""
    specs: dict[str, list[str]] = {}
    manager_df = repo_root / "manager-web" / "Dockerfile"
    if manager_df.is_file():
        specs["arb-manager-web:local"] = [
            "docker",
            "build",
            "-f",
            "manager-web/Dockerfile",
            "-t",
            "arb-manager-web:local",
            ".",
        ]
    return specs


def phase_build_images(config: AppConfig, *, no_cache: bool) -> JpResult[PhaseOutcome]:
    build_specs = _repo_docker_build_specs(config.repo_root)
    if build_specs:
        for _local_tag, cmd in build_specs.items():
            if no_cache:
                cmd = [*cmd[:2], "--no-cache", *cmd[2:]]
            built = run_command_checked(cmd, cwd=config.repo_root)
            if isinstance(built, Failure):
                return built
        built_tags = list(build_specs.keys())
    else:
        build_script = config.repo_root / "make" / "build_docker.py"
        if build_script.is_file():
            cmd = ["python3", str(build_script)]
            if no_cache:
                cmd.append("--no-cache")
            built = run_command_checked(cmd, cwd=config.repo_root)
            if isinstance(built, Failure):
                return built
            built_tags = list(LOCAL_IMAGES.values())
        else:
            legacy = (
                config.repo_root / "infra" / "aws" / "containers" / "scripts" / "rebuild_all.py"
            )
            if not legacy.is_file():
                return Success(
                    PhaseOutcome(
                        name="build_images",
                        ok=False,
                        detail=(
                            "No buildable Docker images in repo and no "
                            "make/build_docker.py or rebuild_all.py. Use --skip-build."
                        ),
                    ),
                )
            cmd = ["python3", str(legacy), "--build-only"]
            if no_cache:
                cmd.append("--no-cache")
            built = run_command_checked(cmd, cwd=config.repo_root)
            if isinstance(built, Failure):
                return built
            built_tags = list(LOCAL_IMAGES.values())

    missing = [tag for tag in built_tags if docker_image_missing(tag, cwd=config.repo_root)]
    if missing:
        return Success(
            PhaseOutcome(
                name="build_images",
                ok=False,
                detail=f"missing images: {', '.join(missing)}",
            ),
        )
    return Success(
        PhaseOutcome(
            name="build_images",
            ok=True,
            detail=f"built {len(built_tags)} images",
        ),
    )


def phase_ecr_push(
    config: AppConfig,
    *,
    ecr_urls: dict[str, str],
    image_tag: str,
) -> JpResult[PhaseOutcome]:
    registry = f"{config.aws.AccountId}.dkr.ecr.{config.aws.Region}.amazonaws.com"
    login = run_command_checked(
        [
            "aws",
            "ecr",
            "get-login-password",
            "--profile",
            config.aws.Profile,
            "--region",
            config.aws.Region,
        ],
        cwd=config.repo_root,
    )
    if isinstance(login, Failure):
        return login

    import subprocess

    try:
        subprocess.run(
            ["docker", "login", "--username", "AWS", "--password-stdin", registry],
            input=login.unwrap().stdout.strip(),
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        return Failure(
            AppError(
                code=ErrorCodes.DEPLOY,
                message="Docker ECR login failed.",
                detail=str(exc),
            ),
        )

    pushed: list[str] = []
    skipped: list[str] = []
    for workload_key, local_ref in LOCAL_IMAGES.items():
        repo_url = ecr_urls.get(workload_key)
        if not repo_url:
            skipped.append(workload_key)
            continue
        if docker_image_missing(local_ref, cwd=config.repo_root):
            skipped.append(workload_key)
            continue
        remote = f"{repo_url}:{image_tag}"
        tagged = run_command_checked(
            ["docker", "tag", local_ref, remote],
            cwd=config.repo_root,
        )
        if isinstance(tagged, Failure):
            return tagged
        pushed_result = run_command_checked(["docker", "push", remote], cwd=config.repo_root)
        if isinstance(pushed_result, Failure):
            return pushed_result
        pushed.append(remote)

    if not pushed:
        return Success(
            PhaseOutcome(
                name="ecr_push",
                ok=False,
                detail="no images pushed — run terraform apply first",
            ),
        )
    detail = f"pushed {len(pushed)} images ({image_tag})"
    if skipped:
        detail += f"; skipped {len(skipped)} (no ECR repo)"
    return Success(PhaseOutcome(name="ecr_push", ok=True, detail=detail))


def _helm_shared_mount_args(spec: dict[str, object]) -> list[str]:
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
        s3_volume = spec.get("s3_shared_volume_name", "shared-s3-files")
        s3_mount = spec.get("s3_shared_mount_path", "/mnt/s3-files")
        args.extend(
            [
                "--set",
                "s3SharedFiles.enabled=true",
                "--set",
                f"s3SharedFiles.volumeName={s3_volume}",
                "--set",
                f"s3SharedFiles.mountPath={s3_mount}",
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
    drop = frozenset(
        {
            "AWS_ACCESS_KEY_ID",
            "AWS_SECRET_ACCESS_KEY",
            "AWS_PROFILE",
            "AWS_DEFAULT_PROFILE",
        },
    )
    args: list[str] = []
    for key, value in sorted(env_map.items()):
        if key in drop:
            continue
        args.extend(["--set", f"env.{key}={value}"])
    return args


def phase_helm_rollout(
    config: AppConfig,
    *,
    outputs: dict[str, Any],
    image_tag: str,
    workload_keys: Option[list[str]] = None,
) -> JpResult[PhaseOutcome]:
    deploy_specs = outputs.get("containers_workload_deploy_specs", {}).get("value") or {}
    if not deploy_specs:
        return Success(
            PhaseOutcome(
                name="helm_rollout",
                ok=False,
                detail="missing containers_workload_deploy_specs terraform output",
            ),
        )

    keys = workload_keys or sorted(deploy_specs.keys())
    namespace = (
        outputs.get("containers_k8s_namespace", {}).get("value") or config.paths.K8sNamespace
    ).strip()

    cluster = outputs.get("containers_eks_cluster_name", {}).get("value") or ""
    if not cluster:
        return Success(
            PhaseOutcome(
                name="helm_rollout",
                ok=False,
                detail="missing containers_eks_cluster_name terraform output",
            ),
        )

    kubeconfig = run_command_checked(
        [
            "aws",
            "eks",
            "update-kubeconfig",
            "--name",
            str(cluster),
            "--profile",
            config.aws.Profile,
            "--region",
            config.aws.Region,
        ],
        cwd=config.repo_root,
    )
    if isinstance(kubeconfig, Failure):
        return kubeconfig

    chart_dir = config.helm_chart_dir
    if not chart_dir.is_dir():
        return Success(
            PhaseOutcome(
                name="helm_rollout",
                ok=False,
                detail=(f"missing Helm chart at {chart_dir.relative_to(config.repo_root)}"),
            ),
        )

    released: list[str] = []
    for workload_key in keys:
        spec = deploy_specs.get(workload_key)
        if not spec:
            continue
        release = spec.get("k8s_service_name") or workload_key.replace("_", "-")
        image = spec.get("image") or ""
        if not image or ":" not in image:
            return Success(
                PhaseOutcome(
                    name="helm_rollout",
                    ok=False,
                    detail=f"{workload_key}: invalid image {image!r}",
                ),
            )
        repo, _ = image.rsplit(":", 1)
        role_arn = spec.get("task_role_arn") or ""
        sa_annotations = (
            f"serviceAccount.annotations.eks\\.amazonaws\\.com/role-arn={role_arn}"
            if role_arn
            else ""
        )
        expose_lb = "true" if spec.get("expose_load_balancer") else "false"
        cmd = [
            "helm",
            "upgrade",
            "--install",
            release,
            str(chart_dir),
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
            f"image.tag={image_tag}",
            "--set",
            f"service.port={spec.get('container_port', 8080)}",
            "--set",
            f"service.exposeLoadBalancer={expose_lb}",
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
        helm = run_command_checked(cmd, cwd=config.repo_root)
        if isinstance(helm, Failure):
            return helm
        released.append(release)

    if not released:
        return Success(
            PhaseOutcome(
                name="helm_rollout",
                ok=False,
                detail="no Helm releases upgraded",
            ),
        )
    return Success(
        PhaseOutcome(
            name="helm_rollout",
            ok=True,
            detail=f"{len(released)} releases upgraded in {namespace}",
        ),
    )


def http_ok(url: str, *, timeout_s: float = 10.0) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout_s) as resp:  # noqa: S310
            return 200 <= resp.status < 500
    except (urllib.error.URLError, TimeoutError):
        return False


def _manager_web_load_balancer_host(config: AppConfig, namespace: str) -> str:
    for resource, name in (("ingress", "manager-web"), ("svc", "manager-web")):
        proc = run_command_checked(
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
            cwd=config.repo_root,
        )
        if isinstance(proc, Failure):
            continue
        host = proc.unwrap().stdout.strip()
        if host:
            return host
    return ""


def phase_aws_validate(
    config: AppConfig,
    *,
    outputs: dict[str, Any],
    alb_timeout_s: int,
) -> JpResult[PhaseOutcome]:
    namespace = (
        outputs.get("containers_k8s_namespace", {}).get("value") or config.paths.K8sNamespace
    ).strip()
    deadline = time.monotonic() + alb_timeout_s
    while time.monotonic() < deadline:
        host = _manager_web_load_balancer_host(config, namespace)
        if host:
            url = f"http://{host}/"
            if http_ok(url):
                return Success(
                    PhaseOutcome(
                        name="aws_validate",
                        ok=True,
                        detail=f"manager-web at {url}",
                        data={"manager_web_url": url},
                    ),
                )
        time.sleep(15)
    return Success(
        PhaseOutcome(
            name="aws_validate",
            ok=False,
            detail=f"manager-web not reachable within {alb_timeout_s}s",
        ),
    )

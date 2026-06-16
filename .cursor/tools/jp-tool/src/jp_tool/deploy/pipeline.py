"""Deploy pipeline orchestration."""

from __future__ import annotations

from collections.abc import Callable

from jp_tool.core.config import AppConfig, load_app_config
from jp_tool.core.errors import AppError, ErrorCodes
from jp_tool.core.option import Option
from jp_tool.core.results import Failure, Success
from jp_tool.core.types import JpResult
from jp_tool.deploy.models import DeployInvokeParams, DeploySummary, PhaseOutcome
from jp_tool.deploy.phases import (
    default_image_tag,
    phase_aws_validate,
    phase_build_images,
    phase_configure_aws,
    phase_ecr_push,
    phase_helm_rollout,
    phase_preflight,
    phase_terraform,
    phase_validate_secrets,
)

PhaseFn = Callable[[], JpResult[PhaseOutcome]]


def merge_invoke_params(config: AppConfig, params: DeployInvokeParams) -> DeployInvokeParams:
    """Overlay CLI overrides onto config defaults."""
    return DeployInvokeParams(
        auto_approve=params.auto_approve
        if params.auto_approve is not None
        else config.deploy.AutoApprove,
        skip_build=params.skip_build if params.skip_build is not None else config.deploy.SkipBuild,
        skip_scaffold=params.skip_scaffold
        if params.skip_scaffold is not None
        else config.deploy.SkipScaffold,
        skip_preflight=params.skip_preflight
        if params.skip_preflight is not None
        else config.deploy.SkipPreflight,
        image_tag=params.image_tag if params.image_tag is not None else config.deploy.ImageTag,
        no_cache=params.no_cache if params.no_cache is not None else config.deploy.NoCache,
        post_terraform_only=params.post_terraform_only,
    )


def run_phases(phases: list[tuple[str, PhaseFn]]) -> JpResult[DeploySummary]:
    """Execute phases sequentially; stop on first failure."""
    outcomes: list[PhaseOutcome] = []
    manager_web_url = ""

    for name, fn in phases:
        result = fn()
        if isinstance(result, Failure):
            return result
        outcome = result.unwrap()
        if outcome.name != name:
            outcome = PhaseOutcome(
                name=name,
                ok=outcome.ok,
                detail=outcome.detail,
                data=outcome.data,
            )
        outcomes.append(outcome)
        if not outcome.ok:
            return Success(
                DeploySummary(
                    phases=tuple(outcomes),
                    success=False,
                    manager_web_url=manager_web_url,
                ),
            )
        manager_web_url = str(outcome.data.get("manager_web_url") or manager_web_url)

    return Success(
        DeploySummary(
            phases=tuple(outcomes),
            success=all(item.ok for item in outcomes),
            manager_web_url=manager_web_url,
        ),
    )


def build_phase_list(
    config: AppConfig,
    params: DeployInvokeParams,
    *,
    tf_outputs: Option[dict[str, object]] = None,
    ecr_urls: Option[dict[str, str]] = None,
) -> list[tuple[str, PhaseFn]]:
    """Construct ordered deploy phases from config and invoke params."""
    tag = default_image_tag(params.image_tag)
    outputs: dict[str, object] = dict(tf_outputs or {})
    repos: dict[str, str] = dict(ecr_urls or {})

    def _terraform_phase() -> JpResult[PhaseOutcome]:
        result = phase_terraform(
            config,
            auto_approve=bool(params.auto_approve),
            image_tag=tag,
        )
        if isinstance(result, Failure):
            return result
        outcome = result.unwrap()
        if outcome.ok:
            outputs.update(outcome.data.get("outputs") or {})
            repos.update(outcome.data.get("ecr_urls") or {})
        return Success(outcome)

    phases: list[tuple[str, PhaseFn]] = [
        ("configure_aws", lambda: phase_configure_aws(config)),
    ]
    if not params.skip_preflight:
        phases.append(("preflight", lambda: phase_preflight(config)))
    if not params.post_terraform_only:
        if not params.skip_scaffold:
            phases.append(
                (
                    "scaffold_secrets",
                    lambda: Success(
                        PhaseOutcome(
                            name="scaffold_secrets",
                            ok=True,
                            detail="skipped — run make/scaffold_secrets.py separately",
                        ),
                    ),
                ),
            )
        phases.extend(
            [
                ("validate_secrets", lambda: phase_validate_secrets(config)),
                ("terraform", _terraform_phase),
            ],
        )
    if not params.skip_build:
        phases.append(
            (
                "build_images",
                lambda: phase_build_images(config, no_cache=bool(params.no_cache)),
            ),
        )
    phases.extend(
        [
            (
                "ecr_push",
                lambda: (
                    phase_ecr_push(config, ecr_urls=repos, image_tag=tag)
                    if repos
                    else Success(
                        PhaseOutcome(
                            name="ecr_push",
                            ok=False,
                            detail="no ECR URLs — run terraform phase first",
                        ),
                    )
                ),
            ),
            (
                "helm_rollout",
                lambda: (
                    phase_helm_rollout(
                        config,
                        outputs=outputs,
                        image_tag=tag,
                        workload_keys=sorted(repos.keys()) if repos else None,
                    )
                    if outputs
                    else Success(
                        PhaseOutcome(
                            name="helm_rollout",
                            ok=False,
                            detail=("missing terraform outputs — run terraform phase first"),
                        ),
                    )
                ),
            ),
            (
                "aws_validate",
                lambda: (
                    phase_aws_validate(
                        config,
                        outputs=outputs,
                        alb_timeout_s=config.deploy.AlbTimeout,
                    )
                    if outputs
                    else Success(
                        PhaseOutcome(
                            name="aws_validate",
                            ok=False,
                            detail=("missing terraform outputs — run terraform phase first"),
                        ),
                    )
                ),
            ),
        ],
    )
    return phases


def execute_deploy(
    config: AppConfig,
    params: DeployInvokeParams,
) -> JpResult[DeploySummary]:
    """Run the full or post-terraform deploy pipeline."""
    merged = merge_invoke_params(config, params)

    if merged.post_terraform_only:
        tf_dir = config.terraform_dir
        from jp_tool.core.subprocess_runner import run_json_command

        outputs_result = run_json_command(["terraform", "output", "-json"], cwd=tf_dir)
        if isinstance(outputs_result, Failure):
            return outputs_result
        payload = outputs_result.unwrap()
        ecr = payload.get("containers_ecr_repository_urls", {}).get("value") or {}
        if not ecr:
            return Failure(
                AppError(
                    code=ErrorCodes.TERRAFORM,
                    message="Terraform outputs missing ECR URLs.",
                    detail="Run terraform apply before post-terraform deploy.",
                ),
            )
        phases = build_phase_list(
            config,
            merged,
            tf_outputs=payload,
            ecr_urls=ecr,
        )
        # Drop infra-only phases for post-terraform mode
        skip = {
            "configure_aws",
            "preflight",
            "scaffold_secrets",
            "validate_secrets",
            "terraform",
        }
        phases = [item for item in phases if item[0] not in skip]
        return run_phases(phases)

    phases = build_phase_list(config, merged)
    return run_phases(phases)


def load_config_and_deploy(
    params: DeployInvokeParams,
    *,
    config_path: Option[object] = None,
) -> JpResult[DeploySummary]:
    """Load ``app_config.toml`` then execute deploy."""
    from pathlib import Path

    resolved_path = Path(config_path) if isinstance(config_path, Path) else None
    config_result = load_app_config(config_path=resolved_path)
    if isinstance(config_result, Failure):
        return config_result
    return execute_deploy(config_result.unwrap(), params)


def format_summary(summary: DeploySummary) -> str:
    """Render human-readable deploy summary."""
    lines = ["=== Deploy summary ==="]
    for phase in summary.phases:
        status = "OK" if phase.ok else "FAIL"
        lines.append(f"  [{status}] {phase.name}: {phase.detail}")
    if summary.success and summary.manager_web_url:
        lines.append("")
        lines.append(f"Manager web URL: {summary.manager_web_url}")
    lines.append("")
    lines.append(f"Result: {'SUCCESS' if summary.success else 'FAILED'}")
    return "\n".join(lines)

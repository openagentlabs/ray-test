"""Deploy action — full AWS pipeline."""

from __future__ import annotations

from typing import ClassVar

import typer

from deploy_to_aws.actions.action_base import ActionBase
from deploy_to_aws.core.config import load_app_config
from deploy_to_aws.core.results import Failure, Success
from deploy_to_aws.core.types import TextResult, UnitResult
from deploy_to_aws.core.validation import parse_invoke_model
from deploy_to_aws.deploy.models import DeployInvokeParams
from deploy_to_aws.deploy.pipeline import execute_deploy, format_summary


class DeployAction(ActionBase):
    """Run Terraform → build → ECR → Helm → validation."""

    ID: ClassVar[str] = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
    NAME: ClassVar[str] = "deploy"
    DESCRIPTION: ClassVar[str] = "Full AWS deploy pipeline for the configured APP_ENV."
    VERSION: ClassVar[str] = "0.1.0"

    def invoke(self, **kwargs: object) -> TextResult:
        parsed = parse_invoke_model(
            DeployInvokeParams,
            kwargs,
            message="Invalid deploy invoke parameters.",
        )
        if isinstance(parsed, Failure):
            return parsed

        config_result = load_app_config()
        if isinstance(config_result, Failure):
            return Failure(config_result.failure())

        summary_result = execute_deploy(config_result.unwrap(), parsed.unwrap())
        if isinstance(summary_result, Failure):
            return Failure(summary_result.failure())
        return Success(format_summary(summary_result.unwrap()))

    def bind_cli(self, app: typer.Typer) -> UnitResult:
        action = self

        @app.command(name=self.NAME, help=self.DESCRIPTION)
        def deploy_cmd(
            yes: bool | None = typer.Option(
                None, "--yes", help="Auto-approve terraform apply."
            ),
            skip_build: bool | None = typer.Option(
                None, "--skip-build", help="Skip Docker build."
            ),
            skip_scaffold: bool | None = typer.Option(
                None,
                "--skip-scaffold",
                help="Skip secrets scaffold phase.",
            ),
            skip_preflight: bool | None = typer.Option(
                None,
                "--skip-preflight",
                help="Skip tool and AWS preflight checks.",
            ),
            image_tag: str | None = typer.Option(
                None,
                "--image-tag",
                help="Override container image tag.",
            ),
            no_cache: bool | None = typer.Option(
                None,
                "--no-cache",
                help="Build Docker images without cache.",
            ),
        ) -> None:
            result = action.invoke(
                auto_approve=yes,
                skip_build=skip_build,
                skip_scaffold=skip_scaffold,
                skip_preflight=skip_preflight,
                image_tag=image_tag,
                no_cache=no_cache,
                post_terraform_only=False,
            )
            if isinstance(result, Failure):
                from deploy_to_aws.core.cli_output import die_json_error

                die_json_error(result.failure())
            print(result.unwrap())

        return Success(None)


class PostDeployAction(ActionBase):
    """Post-Terraform only: build → ECR → Helm → validate."""

    ID: ClassVar[str] = "b2c3d4e5-f6a7-8901-bcde-f12345678901"
    NAME: ClassVar[str] = "post-deploy"
    DESCRIPTION: ClassVar[str] = (
        "Run build, ECR push, Helm rollout after terraform apply."
    )
    VERSION: ClassVar[str] = "0.1.0"

    def invoke(self, **kwargs: object) -> TextResult:
        parsed = parse_invoke_model(
            DeployInvokeParams,
            kwargs,
            message="Invalid post-deploy invoke parameters.",
        )
        if isinstance(parsed, Failure):
            return parsed

        params = parsed.unwrap().model_copy(update={"post_terraform_only": True})
        config_result = load_app_config()
        if isinstance(config_result, Failure):
            return Failure(config_result.failure())

        summary_result = execute_deploy(config_result.unwrap(), params)
        if isinstance(summary_result, Failure):
            return Failure(summary_result.failure())
        return Success(format_summary(summary_result.unwrap()))

    def bind_cli(self, app: typer.Typer) -> UnitResult:
        action = self

        @app.command(name=self.NAME, help=self.DESCRIPTION)
        def post_deploy_cmd(
            skip_build: bool | None = typer.Option(
                None, "--skip-build", help="Skip Docker build."
            ),
            image_tag: str | None = typer.Option(
                None,
                "--image-tag",
                help="Override container image tag.",
            ),
            no_cache: bool | None = typer.Option(
                None,
                "--no-cache",
                help="Build Docker images without cache.",
            ),
        ) -> None:
            result = action.invoke(
                skip_build=skip_build,
                image_tag=image_tag,
                no_cache=no_cache,
                post_terraform_only=True,
            )
            if isinstance(result, Failure):
                from deploy_to_aws.core.cli_output import die_json_error

                die_json_error(result.failure())
            print(result.unwrap())

        return Success(None)

"""Cloud-provider registry list action."""

from __future__ import annotations

import typer
from returns.result import Failure

from tf_tool.actions.action_base import ActionBase
from tf_tool.actions.registry_search.constants import DEFAULT_LIMIT
from tf_tool.actions.registry_search.list import list_registry_modules
from tf_tool.actions.registry_search.list_cli import run_list_command
from tf_tool.actions.registry_search.validation import (
    parse_cloud_list_invoke,
    validate_list_request,
)
from tf_tool.core.cli_output import die_json_error
from tf_tool.core.help_text import (
    OPT_JSON,
    OPT_LIMIT,
    OPT_NAMESPACE,
    OPT_OFFSET,
    OPT_PROVIDER_REQUIRED,
    OPT_VERIFIED,
    cloud_list_examples,
)
from tf_tool.core.results import Success
from tf_tool.core.types import TextResult, UnitResult


class CloudRegistryListAction(ActionBase):
    """List Terraform modules for a named cloud provider."""

    ID = "b9f4d6e2-5a8c-4b3f-0d27-6c5e9f3b2d04"
    NAME = "list-cloud"
    DESCRIPTION = "Browse modules for one cloud provider (-p required)."
    VERSION = "0.1.0"

    def invoke(self, **kwargs: object) -> TextResult:
        parsed = parse_cloud_list_invoke(kwargs)
        if isinstance(parsed, Failure):
            return parsed
        params = parsed.unwrap()
        validated = validate_list_request(
            provider=params.provider,
            namespace=params.namespace,
            verified=params.verified,
            limit=params.limit,
            offset=params.offset,
        )
        if isinstance(validated, Failure):
            return validated
        request = validated.unwrap()
        return list_registry_modules(
            provider=request.provider,
            namespace=request.namespace,
            verified=request.verified,
            limit=request.limit,
            offset=request.offset,
        )

    def bind_cli(self, app: typer.Typer) -> UnitResult:
        @app.command(
            self.NAME,
            help=self.DESCRIPTION,
            epilog=cloud_list_examples(),
        )
        def _list_cloud_cmd(
            provider: str = typer.Option(..., "-p", "--provider", help=OPT_PROVIDER_REQUIRED),
            namespace: str | None = typer.Option(None, "--namespace", help=OPT_NAMESPACE),
            verified: bool | None = typer.Option(
                None,
                "--verified/--all",
                help=OPT_VERIFIED,
            ),
            limit: int = typer.Option(
                DEFAULT_LIMIT,
                "--limit",
                min=1,
                max=100,
                help=OPT_LIMIT,
            ),
            offset: int = typer.Option(0, "--offset", min=0, help=OPT_OFFSET),
            json_output: bool = typer.Option(False, "--json", help=OPT_JSON),
        ) -> None:
            validated = validate_list_request(
                provider=provider,
                namespace=namespace,
                verified=verified,
                limit=limit,
                offset=offset,
            )
            if isinstance(validated, Failure):
                die_json_error(validated.failure())
                return
            run_list_command(validated.unwrap(), json_output=json_output)

        return Success(None)

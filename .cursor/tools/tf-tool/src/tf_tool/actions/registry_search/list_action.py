"""Registry list action (browse modules without keyword)."""

from __future__ import annotations

import typer
from returns.result import Failure

from tf_tool.actions.action_base import ActionBase
from tf_tool.actions.registry_search.constants import DEFAULT_LIMIT
from tf_tool.actions.registry_search.list import list_registry_modules
from tf_tool.actions.registry_search.list_cli import run_list_command
from tf_tool.actions.registry_search.validation import (
    parse_registry_list_invoke,
    validate_list_request,
)
from tf_tool.core.cli_output import die_json_error
from tf_tool.core.help_text import (
    OPT_JSON,
    OPT_LIMIT,
    OPT_NAMESPACE,
    OPT_OFFSET,
    OPT_PROVIDER,
    OPT_VERIFIED,
    list_examples,
)
from tf_tool.core.results import Success
from tf_tool.core.types import TextResult, UnitResult


class RegistryListAction(ActionBase):
    """List Terraform modules on registry.terraform.io (no keyword required)."""

    ID = "a8e3c5d1-4f7b-4a2e-9c16-5b4d8e2f1a93"
    NAME = "registry-list"
    DESCRIPTION = "Browse registry modules; download by row number."
    VERSION = "0.1.0"

    def invoke(self, **kwargs: object) -> TextResult:
        parsed = parse_registry_list_invoke(kwargs)
        if isinstance(parsed, Failure):
            return parsed
        params = parsed.unwrap()
        return list_registry_modules(
            provider=params.provider,
            namespace=params.namespace,
            verified=params.verified,
            limit=params.limit,
            offset=params.offset,
        )

    def bind_cli(self, app: typer.Typer) -> UnitResult:
        @app.command(
            self.NAME,
            help=self.DESCRIPTION,
            epilog=list_examples("registry-list"),
        )
        def _registry_list_cmd(
            provider: str | None = typer.Option(None, "-p", "--provider", help=OPT_PROVIDER),
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

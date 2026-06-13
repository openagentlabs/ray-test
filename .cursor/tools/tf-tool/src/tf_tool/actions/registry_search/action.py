"""Registry search action."""

from __future__ import annotations

import typer
from returns.result import Failure

from tf_tool.actions.action_base import ActionBase
from tf_tool.actions.registry_search.constants import DEFAULT_LIMIT
from tf_tool.actions.registry_search.search import search_registry_modules
from tf_tool.actions.registry_search.validation import (
    parse_registry_search_invoke,
    validate_search_request,
)
from tf_tool.core.cli_output import die_json_error, emit_action
from tf_tool.core.command_label import argv_command_label
from tf_tool.core.help_text import (
    OPT_LIMIT,
    OPT_NAMESPACE,
    OPT_OFFSET,
    OPT_PROVIDER,
    OPT_QUERY,
    OPT_VERIFIED,
    search_examples,
)
from tf_tool.core.results import Success
from tf_tool.core.types import TextResult, UnitResult


class RegistrySearchAction(ActionBase):
    """Search Terraform modules on the public registry."""

    ID = "b7e4d2a1-5c38-4f9e-9a12-3d8f6b2e4c71"
    NAME = "registry-search"
    DESCRIPTION = "Search registry modules by keyword."
    VERSION = "0.1.0"

    def invoke(self, **kwargs: object) -> TextResult:
        parsed = parse_registry_search_invoke(kwargs)
        if isinstance(parsed, Failure):
            return parsed
        params = parsed.unwrap()
        return search_registry_modules(
            query=params.query,
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
            epilog=search_examples("registry-search"),
        )
        def _registry_search_cmd(
            query: str = typer.Option(..., "-q", "--query", help=OPT_QUERY),
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
        ) -> None:
            validated = validate_search_request(
                query=query,
                provider=provider,
                namespace=namespace,
                verified=verified,
                limit=limit,
                offset=offset,
            )
            if isinstance(validated, Failure):
                die_json_error(validated.failure())
                return
            request = validated.unwrap()
            emit_action(
                lambda: search_registry_modules(
                    query=request.query,
                    provider=request.provider,
                    namespace=request.namespace,
                    verified=request.verified,
                    limit=request.limit,
                    offset=request.offset,
                ),
                operation="Searching Terraform Registry",
                command=argv_command_label(default="tf-tool registry-search"),
            )

        return Success(None)

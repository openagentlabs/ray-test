"""Base class for provider-scoped Terraform Registry search actions."""

from __future__ import annotations

from abc import ABC
from collections.abc import Callable
from typing import ClassVar

import typer
from returns.result import Failure

from tf_tool.actions.action_base import ActionBase
from tf_tool.actions.registry_search.constants import DEFAULT_LIMIT
from tf_tool.actions.registry_search.validation import (
    parse_provider_search_invoke,
    validate_search_request,
)
from tf_tool.core.cli_output import die_json_error, emit_action
from tf_tool.core.command_label import argv_command_label
from tf_tool.core.help_text import (
    OPT_LIMIT,
    OPT_NAMESPACE,
    OPT_OFFSET,
    OPT_QUERY,
    OPT_VERIFIED,
    primary_command,
    search_examples,
)
from tf_tool.core.results import Success
from tf_tool.core.types import TextResult, UnitResult


class ProviderRegistrySearchAction(ActionBase, ABC):
    """Search Terraform Registry modules for a fixed cloud provider."""

    PROVIDER: ClassVar[str]
    PROVIDER_LABEL: ClassVar[str]
    CLI_ALIASES: ClassVar[tuple[str, ...]] = ()

    def invoke(self, **kwargs: object) -> TextResult:
        from tf_tool.actions.registry_search.search import search_registry_modules

        parsed = parse_provider_search_invoke(kwargs)
        if isinstance(parsed, Failure):
            return parsed
        params = parsed.unwrap()
        return search_registry_modules(
            query=params.query,
            provider=self.PROVIDER,
            namespace=params.namespace,
            verified=params.verified,
            limit=params.limit,
            offset=params.offset,
        )

    def _make_search_handler(self) -> Callable[..., None]:
        def _handler(
            query: str = typer.Option(..., "-q", "--query", help=OPT_QUERY),
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
                provider=self.PROVIDER,
                namespace=namespace,
                verified=verified,
                limit=limit,
                offset=offset,
            )
            if isinstance(validated, Failure):
                die_json_error(validated.failure())
                return
            from tf_tool.actions.registry_search.search import search_registry_modules

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
                operation=f"Searching {self.PROVIDER_LABEL} modules",
                command=argv_command_label(default=f"tf-tool {self.NAME}"),
            )

        return _handler

    def bind_cli(self, app: typer.Typer) -> UnitResult:
        handler = self._make_search_handler()
        command = primary_command(self.NAME, self.CLI_ALIASES)
        epilog = search_examples(command)
        for command_name in (self.NAME, *self.CLI_ALIASES):
            app.command(command_name, help=self.DESCRIPTION, epilog=epilog)(handler)
        return Success(None)

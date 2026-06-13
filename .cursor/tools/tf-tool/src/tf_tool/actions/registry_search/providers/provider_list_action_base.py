"""Base class for provider-scoped Terraform Registry list actions."""

from __future__ import annotations

from abc import ABC
from collections.abc import Callable
from typing import ClassVar

import typer
from returns.result import Failure

from tf_tool.actions.action_base import ActionBase
from tf_tool.actions.registry_search.constants import DEFAULT_LIMIT
from tf_tool.actions.registry_search.list import list_registry_modules
from tf_tool.actions.registry_search.list_cli import run_list_command
from tf_tool.actions.registry_search.validation import (
    parse_provider_list_invoke,
    validate_list_request,
)
from tf_tool.core.cli_output import die_json_error
from tf_tool.core.help_text import (
    OPT_JSON,
    OPT_LIMIT,
    OPT_NAMESPACE,
    OPT_OFFSET,
    OPT_VERIFIED,
    list_examples,
    primary_command,
)
from tf_tool.core.results import Success
from tf_tool.core.types import TextResult, UnitResult


class ProviderRegistryListAction(ActionBase, ABC):
    """List Terraform Registry modules for a fixed cloud provider."""

    PROVIDER: ClassVar[str]
    PROVIDER_LABEL: ClassVar[str]
    CLI_ALIASES: ClassVar[tuple[str, ...]] = ()

    def invoke(self, **kwargs: object) -> TextResult:
        parsed = parse_provider_list_invoke(kwargs)
        if isinstance(parsed, Failure):
            return parsed
        params = parsed.unwrap()
        return list_registry_modules(
            provider=self.PROVIDER,
            namespace=params.namespace,
            verified=params.verified,
            limit=params.limit,
            offset=params.offset,
        )

    def _make_list_handler(self) -> Callable[..., None]:
        def _handler(
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
                provider=self.PROVIDER,
                namespace=namespace,
                verified=verified,
                limit=limit,
                offset=offset,
            )
            if isinstance(validated, Failure):
                die_json_error(validated.failure())
                return
            run_list_command(validated.unwrap(), json_output=json_output)

        return _handler

    def bind_cli(self, app: typer.Typer) -> UnitResult:
        handler = self._make_list_handler()
        command = primary_command(self.NAME, self.CLI_ALIASES)
        epilog = list_examples(command)
        for command_name in (self.NAME, *self.CLI_ALIASES):
            app.command(command_name, help=self.DESCRIPTION, epilog=epilog)(handler)
        return Success(None)

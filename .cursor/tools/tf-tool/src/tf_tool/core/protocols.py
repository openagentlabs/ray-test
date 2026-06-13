"""Public protocol contracts for tf-tool components."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

import typer

from tf_tool.core.types import TextResult, TfResult, UnitResult

if TYPE_CHECKING:
    from tf_tool.actions.registry_search.models import RegistrySearchResponse
    from tf_tool.actions.registry_search.validation import SearchRequest


@runtime_checkable
class Action(Protocol):
    """Contract every CLI action must satisfy."""

    @property
    def id(self) -> str:
        """Stable action UUID."""

    @property
    def name(self) -> str:
        """CLI command name."""

    @property
    def description(self) -> str:
        """Short help text."""

    @property
    def version(self) -> str:
        """Semantic action version."""

    def invoke(self, **kwargs: object) -> TextResult:
        """Run action logic; return stdout text or structured failure."""

    def bind_cli(self, app: typer.Typer) -> UnitResult:
        """Register Typer commands for this action."""

    def register(self, manager: object) -> UnitResult:
        """Register with the application action manager."""


@runtime_checkable
class RegistrySearchService(Protocol):
    """HTTP client contract for registry module search."""

    def search(self, request: SearchRequest) -> TfResult[RegistrySearchResponse]:
        """Execute a registry module search and return a validated response."""


__all__ = (
    "Action",
    "RegistrySearchService",
)

"""Public protocol contracts for jp-tool components."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

import typer

from jp_tool.core.types import TextResult, UnitResult


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


__all__ = ("Action",)

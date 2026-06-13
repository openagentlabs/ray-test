"""Abstract base for tf-tool actions."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, ClassVar

import typer

from tf_tool.core.types import TextResult, UnitResult

if TYPE_CHECKING:
    from tf_tool.action_manager.manager import ActionManager


class ActionBase(ABC):
    """Base class every action module must subclass and register with main."""

    ID: ClassVar[str]
    NAME: ClassVar[str]
    DESCRIPTION: ClassVar[str]
    VERSION: ClassVar[str]

    @property
    def id(self) -> str:
        """Stable UUID for the action."""
        return self.ID

    @property
    def name(self) -> str:
        """CLI command name (flag/subcommand)."""
        return self.NAME

    @property
    def description(self) -> str:
        """Short help text shown in CLI listings."""
        return self.DESCRIPTION

    @property
    def version(self) -> str:
        """Semantic version for the action implementation."""
        return self.VERSION

    def register(self, manager: ActionManager) -> UnitResult:
        """Register this action with the application action manager."""
        return manager.register(self)

    @abstractmethod
    def invoke(self, **kwargs: object) -> TextResult:
        """Run the action logic and return output text or a structured error."""

    @abstractmethod
    def bind_cli(self, app: typer.Typer) -> UnitResult:
        """Register Typer flags/commands for this action."""

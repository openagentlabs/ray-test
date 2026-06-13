"""Abstract base for deploy-to-aws actions."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, ClassVar

import typer

from deploy_to_aws.core.types import TextResult, UnitResult

if TYPE_CHECKING:
    from deploy_to_aws.action_manager.manager import ActionManager


class ActionBase(ABC):
    """Base class every action module must subclass and register."""

    ID: ClassVar[str]
    NAME: ClassVar[str]
    DESCRIPTION: ClassVar[str]
    VERSION: ClassVar[str]

    @property
    def id(self) -> str:
        return self.ID

    @property
    def name(self) -> str:
        return self.NAME

    @property
    def description(self) -> str:
        return self.DESCRIPTION

    @property
    def version(self) -> str:
        return self.VERSION

    def register(self, manager: ActionManager) -> UnitResult:
        return manager.register(self)

    @abstractmethod
    def invoke(self, **kwargs: object) -> TextResult:
        """Run action logic and return output text or structured error."""

    @abstractmethod
    def bind_cli(self, app: typer.Typer) -> UnitResult:
        """Register Typer commands for this action."""

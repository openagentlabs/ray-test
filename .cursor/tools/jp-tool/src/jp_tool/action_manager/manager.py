"""Register and invoke jp-tool actions."""

from __future__ import annotations

import typer

from jp_tool.actions.action_base import ActionBase
from jp_tool.core.errors import AppError, ErrorCodes
from jp_tool.core.results import Failure, Success
from jp_tool.core.types import TextResult, UnitResult


class ActionManager:
    """Stores registered actions and dispatches invoke requests by name."""

    def __init__(self, app: typer.Typer) -> None:
        self._app = app
        self._actions: dict[str, ActionBase] = {}

    def register(self, action: ActionBase) -> UnitResult:
        if action.name in self._actions:
            return Failure(
                AppError(
                    code=ErrorCodes.DUPLICATE,
                    message="Action name already registered.",
                    detail=f"Duplicate action name: {action.name!r}.",
                ),
            )
        bound = action.bind_cli(self._app)
        if isinstance(bound, Failure):
            return bound
        self._actions[action.name] = action
        return Success(None)

    def invoke(self, action_name: str, **kwargs: object) -> TextResult:
        action = self._actions.get(action_name)
        if action is None:
            return Failure(
                AppError(
                    code=ErrorCodes.NOT_FOUND,
                    message="Action not found.",
                    detail=f"No registered action named {action_name!r}.",
                ),
            )
        return action.invoke(**kwargs)

    def list_actions(self) -> tuple[ActionBase, ...]:
        return tuple(self._actions[name] for name in sorted(self._actions))

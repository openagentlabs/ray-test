"""Register all built-in actions."""

from __future__ import annotations

from jp_tool.action_manager.manager import ActionManager
from jp_tool.actions.deploy.action import DeployAction, PostDeployAction
from jp_tool.actions.doctor import DoctorAction
from jp_tool.core.results import Failure, Success
from jp_tool.core.types import UnitResult


def register_all_actions(manager: ActionManager) -> UnitResult:
    actions = (DoctorAction(), DeployAction(), PostDeployAction())
    for action in actions:
        registered = action.register(manager)
        if isinstance(registered, Failure):
            return registered
    return Success(None)

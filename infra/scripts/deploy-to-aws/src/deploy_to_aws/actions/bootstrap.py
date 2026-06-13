"""Register all built-in actions."""

from __future__ import annotations

from deploy_to_aws.action_manager.manager import ActionManager
from deploy_to_aws.actions.deploy.action import DeployAction, PostDeployAction
from deploy_to_aws.core.results import Failure, Success
from deploy_to_aws.core.types import UnitResult


def register_all_actions(manager: ActionManager) -> UnitResult:
    actions = (DeployAction(), PostDeployAction())
    for action in actions:
        registered = action.register(manager)
        if isinstance(registered, Failure):
            return registered
    return Success(None)

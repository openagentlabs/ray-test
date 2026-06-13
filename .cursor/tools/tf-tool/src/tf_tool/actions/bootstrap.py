"""Register all built-in actions with the application manager."""

from __future__ import annotations

from tf_tool.action_manager.manager import ActionManager
from tf_tool.actions.doctor import DoctorAction
from tf_tool.actions.helloworld import HelloWorldAction
from tf_tool.actions.registry_search import RegistrySearchAction
from tf_tool.actions.registry_search.cloud_action import CloudRegistrySearchAction
from tf_tool.actions.registry_search.list_action import RegistryListAction
from tf_tool.actions.registry_search.list_cloud_action import CloudRegistryListAction
from tf_tool.actions.registry_search.providers.aws import (
    AwsRegistryListAction,
    AwsRegistrySearchAction,
)
from tf_tool.actions.registry_search.providers.azurerm import AzurermRegistrySearchAction
from tf_tool.actions.registry_search.providers.google import GoogleRegistrySearchAction
from tf_tool.core.results import Failure, Success
from tf_tool.core.types import UnitResult


def register_all_actions(manager: ActionManager) -> UnitResult:
    """Register every action module with the shared manager."""
    actions = (
        DoctorAction(),
        HelloWorldAction(),
        RegistrySearchAction(),
        RegistryListAction(),
        CloudRegistrySearchAction(),
        CloudRegistryListAction(),
        AwsRegistrySearchAction(),
        AwsRegistryListAction(),
        GoogleRegistrySearchAction(),
        AzurermRegistrySearchAction(),
    )
    for action in actions:
        registered = action.register(manager)
        if isinstance(registered, Failure):
            return registered
    return Success(None)

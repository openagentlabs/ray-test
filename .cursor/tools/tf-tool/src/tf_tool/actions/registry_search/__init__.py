"""Registry search action package."""

from tf_tool.actions.registry_search.action import RegistrySearchAction
from tf_tool.actions.registry_search.cloud_action import CloudRegistrySearchAction
from tf_tool.actions.registry_search.filters import RegistrySearchFilters
from tf_tool.actions.registry_search.providers.aws import (
    AwsRegistrySearchAction,
    search_aws_modules,
)
from tf_tool.actions.registry_search.providers.azurerm import (
    AzurermRegistrySearchAction,
    search_azurerm_modules,
)
from tf_tool.actions.registry_search.providers.catalog import (
    CLOUD_PROVIDER_CATALOG,
    resolve_cloud_provider,
)
from tf_tool.actions.registry_search.providers.google import (
    GoogleRegistrySearchAction,
    search_google_modules,
)
from tf_tool.actions.registry_search.search import search_registry_modules

__all__ = (
    "AwsRegistrySearchAction",
    "AzurermRegistrySearchAction",
    "CLOUD_PROVIDER_CATALOG",
    "CloudRegistrySearchAction",
    "GoogleRegistrySearchAction",
    "RegistrySearchAction",
    "RegistrySearchFilters",
    "resolve_cloud_provider",
    "search_aws_modules",
    "search_azurerm_modules",
    "search_google_modules",
    "search_registry_modules",
)

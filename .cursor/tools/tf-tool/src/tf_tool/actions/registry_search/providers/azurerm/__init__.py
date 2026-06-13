"""Azure provider registry search."""

from tf_tool.actions.registry_search.providers.azurerm.action import AzurermRegistrySearchAction
from tf_tool.actions.registry_search.providers.azurerm.search import search_azurerm_modules

__all__ = (
    "AzurermRegistrySearchAction",
    "search_azurerm_modules",
)

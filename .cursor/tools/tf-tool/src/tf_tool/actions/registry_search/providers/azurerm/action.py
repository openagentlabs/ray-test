"""Azure registry search action."""

from __future__ import annotations

from tf_tool.actions.registry_search.providers.azurerm.constants import (
    AZURERM_PROVIDER,
    AZURERM_PROVIDER_LABEL,
)
from tf_tool.actions.registry_search.providers.provider_action_base import (
    ProviderRegistrySearchAction,
)


class AzurermRegistrySearchAction(ProviderRegistrySearchAction):
    """Search Terraform modules for Azure on registry.terraform.io."""

    ID = "e6c0f3a4-9d5f-4a1c-0b34-8f4e1d703c65"
    NAME = "registry-search-azurerm"
    DESCRIPTION = "Search Azure modules by keyword."
    VERSION = "0.1.0"
    PROVIDER = AZURERM_PROVIDER
    PROVIDER_LABEL = AZURERM_PROVIDER_LABEL

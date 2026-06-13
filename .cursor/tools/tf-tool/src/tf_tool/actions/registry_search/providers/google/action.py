"""Google Cloud registry search action."""

from __future__ import annotations

from tf_tool.actions.registry_search.providers.google.constants import (
    GOOGLE_PROVIDER,
    GOOGLE_PROVIDER_LABEL,
)
from tf_tool.actions.registry_search.providers.provider_action_base import (
    ProviderRegistrySearchAction,
)


class GoogleRegistrySearchAction(ProviderRegistrySearchAction):
    """Search Terraform modules for Google Cloud on registry.terraform.io."""

    ID = "d5b9e2f3-8c4e-4f0b-9a23-7e3d0c6f2b54"
    NAME = "registry-search-google"
    DESCRIPTION = "Search Google Cloud modules by keyword."
    VERSION = "0.1.0"
    PROVIDER = GOOGLE_PROVIDER
    PROVIDER_LABEL = GOOGLE_PROVIDER_LABEL

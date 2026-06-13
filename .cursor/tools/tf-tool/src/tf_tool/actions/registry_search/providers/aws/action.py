"""AWS registry search action."""

from __future__ import annotations

from tf_tool.actions.registry_search.providers.aws.constants import (
    AWS_PROVIDER,
    AWS_PROVIDER_LABEL,
)
from tf_tool.actions.registry_search.providers.provider_action_base import (
    ProviderRegistrySearchAction,
)


class AwsRegistrySearchAction(ProviderRegistrySearchAction):
    """Search Terraform modules for the AWS provider on registry.terraform.io."""

    ID = "c4a8f1e2-7b3d-4e9a-8f12-6d2c9b5e1a43"
    NAME = "registry-search-aws"
    CLI_ALIASES = ("search-aws",)
    DESCRIPTION = "Search AWS modules by keyword."
    VERSION = "0.1.0"
    PROVIDER = AWS_PROVIDER
    PROVIDER_LABEL = AWS_PROVIDER_LABEL

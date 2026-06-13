"""AWS registry list action."""

from __future__ import annotations

from tf_tool.actions.registry_search.providers.aws.constants import (
    AWS_PROVIDER,
    AWS_PROVIDER_LABEL,
)
from tf_tool.actions.registry_search.providers.provider_list_action_base import (
    ProviderRegistryListAction,
)


class AwsRegistryListAction(ProviderRegistryListAction):
    """List Terraform modules for AWS on registry.terraform.io."""

    ID = "c1a2b3c4-d5e6-4f78-9a0b-1c2d3e4f5a61"
    NAME = "registry-list-aws"
    CLI_ALIASES = ("list-aws",)
    DESCRIPTION = "Browse AWS modules; download by row number."
    VERSION = "0.1.0"
    PROVIDER = AWS_PROVIDER
    PROVIDER_LABEL = AWS_PROVIDER_LABEL

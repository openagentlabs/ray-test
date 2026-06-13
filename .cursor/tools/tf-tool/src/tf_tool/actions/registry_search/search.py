"""Registry search orchestration.

Gold-standard method for searching modules on the public Terraform Registry:

``GET https://registry.terraform.io/v1/modules/search``

Required query parameter:
- ``q``: keyword or phrase (basic keyword/phrase search on the public registry)

Optional filters:
- ``provider``: cloud provider slug (``aws``, ``google``, ``azurerm``, …)
- ``namespace``: publisher namespace (e.g. ``terraform-aws-modules``)
- ``verified``: ``true`` limits to HashiCorp partner modules
- ``limit`` / ``offset``: pagination (see registry ``meta.next_offset``)

Provider-specific CLI actions under ``registry_search/providers/<cloud>/`` lock
``provider`` and expose one command per cloud (e.g. ``registry-search-aws``).

API reference: https://developer.hashicorp.com/terraform/registry/api-docs#search-modules
Registry UI: https://registry.terraform.io/
"""

from __future__ import annotations

from returns.result import Failure

from tf_tool.actions.registry_search.client import RegistryClient
from tf_tool.actions.registry_search.models import RegistrySearchOutput
from tf_tool.actions.registry_search.validation import SearchRequest, validate_search_request
from tf_tool.core.results import Success
from tf_tool.core.types import TextResult


def search_registry_modules(
    *,
    query: str,
    provider: str | None = None,
    namespace: str | None = None,
    verified: bool | None = None,
    limit: int = 20,
    offset: int = 0,
    client: RegistryClient | None = None,
) -> TextResult:
    """Search the public Terraform Registry and return formatted JSON."""
    validated = validate_search_request(
        query=query,
        provider=provider,
        namespace=namespace,
        verified=verified,
        limit=limit,
        offset=offset,
    )
    if isinstance(validated, Failure):
        return validated

    request: SearchRequest = validated.unwrap()
    registry_client = client or RegistryClient()
    searched = registry_client.search(request)
    if isinstance(searched, Failure):
        return searched

    response = searched.unwrap()
    output = RegistrySearchOutput(
        query=request.query,
        provider=request.provider,
        namespace=request.namespace,
        verified=request.verified,
        limit=request.limit,
        offset=request.offset,
        meta=response.meta,
        modules=response.modules,
        count=len(response.modules),
    )
    return Success(output.model_dump_json(indent=2))

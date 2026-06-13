"""Google Cloud-scoped registry search orchestration."""

from __future__ import annotations

from tf_tool.actions.registry_search.client import RegistrySearchClient
from tf_tool.actions.registry_search.providers.google.constants import GOOGLE_PROVIDER
from tf_tool.actions.registry_search.search import search_registry_modules
from tf_tool.core.types import TextResult


def search_google_modules(
    *,
    query: str,
    namespace: str | None = None,
    verified: bool | None = None,
    limit: int = 20,
    offset: int = 0,
    client: RegistrySearchClient | None = None,
) -> TextResult:
    """Search registry.terraform.io for Google Cloud provider modules."""
    return search_registry_modules(
        query=query,
        provider=GOOGLE_PROVIDER,
        namespace=namespace,
        verified=verified,
        limit=limit,
        offset=offset,
        client=client,
    )

"""Registry list orchestration (browse modules without a keyword).

``GET https://registry.terraform.io/v1/modules``
``GET https://registry.terraform.io/v1/modules/:namespace``

Optional filters: ``provider``, ``verified``, ``limit``, ``offset``.

API reference: https://developer.hashicorp.com/terraform/registry/api-docs#list-modules
"""

from __future__ import annotations

from returns.result import Failure

from tf_tool.actions.registry_search.client import RegistryClient
from tf_tool.actions.registry_search.models import RegistryListOutput
from tf_tool.actions.registry_search.validation import ListRequest, validate_list_request
from tf_tool.core.results import Success
from tf_tool.core.types import TextResult, TfResult


def fetch_registry_list(
    *,
    provider: str | None = None,
    namespace: str | None = None,
    verified: bool | None = None,
    limit: int = 20,
    offset: int = 0,
    client: RegistryClient | None = None,
) -> TfResult[RegistryListOutput]:
    """List Terraform Registry modules and return structured output."""
    validated = validate_list_request(
        provider=provider,
        namespace=namespace,
        verified=verified,
        limit=limit,
        offset=offset,
    )
    if isinstance(validated, Failure):
        return validated

    request: ListRequest = validated.unwrap()
    registry_client = client or RegistryClient()
    listed = registry_client.list_modules(request)
    if isinstance(listed, Failure):
        return listed

    response = listed.unwrap()
    return Success(
        RegistryListOutput(
            provider=request.provider,
            namespace=request.namespace,
            verified=request.verified,
            limit=request.limit,
            offset=request.offset,
            meta=response.meta,
            modules=response.modules,
            count=len(response.modules),
        ),
    )


def list_registry_modules_json(
    *,
    provider: str | None = None,
    namespace: str | None = None,
    verified: bool | None = None,
    limit: int = 20,
    offset: int = 0,
    client: RegistryClient | None = None,
) -> TextResult:
    """List Terraform Registry modules and return formatted JSON."""
    fetched = fetch_registry_list(
        provider=provider,
        namespace=namespace,
        verified=verified,
        limit=limit,
        offset=offset,
        client=client,
    )
    if isinstance(fetched, Failure):
        return fetched
    return Success(fetched.unwrap().model_dump_json(indent=2))


def list_registry_modules(
    *,
    provider: str | None = None,
    namespace: str | None = None,
    verified: bool | None = None,
    limit: int = 20,
    offset: int = 0,
    client: RegistryClient | None = None,
) -> TextResult:
    """Backward-compatible JSON list helper used by action ``invoke``."""
    return list_registry_modules_json(
        provider=provider,
        namespace=namespace,
        verified=verified,
        limit=limit,
        offset=offset,
        client=client,
    )

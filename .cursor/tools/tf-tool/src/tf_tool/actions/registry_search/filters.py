"""Terraform Registry search filter definitions.

The public registry exposes two module-listing surfaces relevant to search:

**Search modules** (keyword search — primary for tf-tool):

``GET https://registry.terraform.io/v1/modules/search``

| Filter | API param | Required | Description |
|--------|-----------|----------|-------------|
| Query | ``q`` | yes | Keyword or phrase |
| Cloud provider | ``provider`` | no | Registry slug (``aws``, ``google``, ``azurerm``, …) |
| Namespace | ``namespace`` | no | Publisher org/user (e.g. ``terraform-aws-modules``) |
| Verified | ``verified`` | no | ``true`` = HashiCorp partner modules only |
| Page size | ``limit`` | no | 1–100 (registry default varies) |
| Offset | ``offset`` | no | Pagination cursor via ``meta.next_offset`` |

**List modules** (browse without keyword — ``registry-list``, ``list-cloud``, ``list-aws``):

``GET https://registry.terraform.io/v1/modules`` or ``.../v1/modules/:namespace``

Supports ``provider``, ``verified``, ``limit``, ``offset`` (no ``q``).

Provider slugs are resolved from friendly cloud names via ``providers/catalog.py``
(``azure`` → ``azurerm``, ``gcp`` → ``google``, etc.).

API reference: https://developer.hashicorp.com/terraform/registry/api-docs
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from tf_tool.actions.registry_search.constants import DEFAULT_LIMIT, MAX_LIMIT, MAX_OFFSET


class RegistrySearchFilters(BaseModel):
    """Canonical filter set for registry module search."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    query: str = Field(..., min_length=1, max_length=200, description="Keyword or phrase (API: q).")
    provider: str | None = Field(
        default=None,
        max_length=64,
        description="Registry provider slug after cloud-name resolution (API: provider).",
    )
    namespace: str | None = Field(
        default=None,
        max_length=128,
        description="Publisher namespace (API: namespace).",
    )
    verified: bool | None = Field(
        default=None,
        description="When true, partner modules only (API: verified).",
    )
    limit: int = Field(
        default=DEFAULT_LIMIT,
        ge=1,
        le=MAX_LIMIT,
        description="Maximum modules returned (API: limit).",
    )
    offset: int = Field(
        default=0,
        ge=0,
        le=MAX_OFFSET,
        description="Pagination offset (API: offset).",
    )

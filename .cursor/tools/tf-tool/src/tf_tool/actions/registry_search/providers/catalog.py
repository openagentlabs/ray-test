"""Cloud provider catalog and name resolution for registry search."""

from __future__ import annotations

import re

from pydantic import BaseModel, ConfigDict, Field

from tf_tool.core.errors import AppError, ErrorCodes
from tf_tool.core.results import Failure, Success
from tf_tool.core.types import TfResult


class CloudProviderDefinition(BaseModel):
    """A cloud platform mapped to a Terraform Registry provider slug."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    registry_slug: str = Field(..., min_length=1, description="Value sent as API provider=.")
    label: str = Field(..., min_length=1, description="Human-readable cloud name.")
    aliases: tuple[str, ...] = Field(
        default_factory=tuple,
        description="Accepted CLI/provider names.",
    )


CLOUD_PROVIDER_CATALOG: tuple[CloudProviderDefinition, ...] = (
    CloudProviderDefinition(
        registry_slug="aws",
        label="AWS",
        aliases=("amazon", "amazon-web-services"),
    ),
    CloudProviderDefinition(
        registry_slug="azurerm",
        label="Azure",
        aliases=("azure", "microsoft", "azure-rm"),
    ),
    CloudProviderDefinition(
        registry_slug="google",
        label="Google Cloud",
        aliases=("gcp", "google-cloud", "googlecloud"),
    ),
    CloudProviderDefinition(
        registry_slug="alicloud",
        label="Alibaba Cloud",
        aliases=("alibaba", "ali-cloud"),
    ),
    CloudProviderDefinition(
        registry_slug="ibm",
        label="IBM Cloud",
        aliases=("ibm-cloud",),
    ),
    CloudProviderDefinition(
        registry_slug="oraclepaas",
        label="Oracle Cloud",
        aliases=("oracle", "oci", "oracle-cloud"),
    ),
    CloudProviderDefinition(
        registry_slug="kubernetes",
        label="Kubernetes",
        aliases=("k8s", "kube"),
    ),
)

_REGISTRY_SLUG_PATTERN = re.compile(r"^[a-z][a-z0-9_-]*$")

_SLUG_INDEX: dict[str, CloudProviderDefinition] = {
    definition.registry_slug: definition for definition in CLOUD_PROVIDER_CATALOG
}

_ALIAS_INDEX: dict[str, str] = {}
for _definition in CLOUD_PROVIDER_CATALOG:
    _ALIAS_INDEX[_definition.registry_slug] = _definition.registry_slug
    for _alias in _definition.aliases:
        _ALIAS_INDEX[_alias] = _definition.registry_slug


def known_provider_names() -> tuple[str, ...]:
    """Return sorted registry slugs and aliases accepted by ``--provider``."""
    names: set[str] = set()
    for definition in CLOUD_PROVIDER_CATALOG:
        names.add(definition.registry_slug)
        names.update(definition.aliases)
    return tuple(sorted(names))


def resolve_cloud_provider(name: str) -> TfResult[str]:
    """Resolve a cloud provider name or alias to a registry provider slug."""
    normalized = name.strip().lower().replace("_", "-")
    if not normalized:
        return Failure(
            AppError(
                code=ErrorCodes.VALIDATION,
                message="Cloud provider name must not be blank.",
                detail=None,
            ),
        )

    slug = _ALIAS_INDEX.get(normalized)
    if slug is not None:
        return Success(slug)

    if _REGISTRY_SLUG_PATTERN.fullmatch(normalized):
        return Success(normalized)

    known = ", ".join(known_provider_names())
    return Failure(
        AppError(
            code=ErrorCodes.VALIDATION,
            message=f"Unknown cloud provider {name!r}.",
            detail=f"Known provider names: {known}",
        ),
    )


def provider_label(registry_slug: str) -> str:
    """Return the display label for a registry slug, or the slug itself."""
    definition = _SLUG_INDEX.get(registry_slug)
    if definition is None:
        return registry_slug
    return definition.label

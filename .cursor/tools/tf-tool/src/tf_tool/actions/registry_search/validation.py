"""Ingress validation for registry search requests."""

from __future__ import annotations

import re
from collections.abc import Mapping

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from tf_tool.actions.registry_search.constants import DEFAULT_LIMIT, MAX_LIMIT, MAX_OFFSET
from tf_tool.actions.registry_search.providers.catalog import resolve_cloud_provider
from tf_tool.core.error_format import format_validation_detail
from tf_tool.core.errors import AppError, ErrorCodes
from tf_tool.core.results import Failure, Success
from tf_tool.core.types import TfResult
from tf_tool.core.validation import parse_invoke_model

_NAMESPACE_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_PROVIDER_SLUG_PATTERN = re.compile(r"^[a-z][a-z0-9_-]*$")


def _normalize_provider(value: str | None) -> str | None:
    if value is None:
        return None
    resolved = resolve_cloud_provider(value)
    if isinstance(resolved, Failure):
        raise ValueError(resolved.failure().detail or resolved.failure().message)
    return resolved.unwrap()


class SearchRequest(BaseModel):
    """Validated registry search parameters sent to the HTTP API."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    query: str = Field(..., min_length=1, max_length=200)
    provider: str | None = Field(default=None, max_length=64)
    namespace: str | None = Field(default=None, max_length=128)
    verified: bool | None = None
    limit: int = Field(default=DEFAULT_LIMIT, ge=1, le=MAX_LIMIT)
    offset: int = Field(default=0, ge=0, le=MAX_OFFSET)

    @field_validator("query")
    @classmethod
    def strip_query(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            msg = "Search query must not be blank."
            raise ValueError(msg)
        return stripped

    @field_validator("provider")
    @classmethod
    def validate_provider(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = _normalize_provider(value)
        if normalized is not None and not _PROVIDER_SLUG_PATTERN.fullmatch(normalized):
            msg = "Resolved provider slug is invalid."
            raise ValueError(msg)
        return normalized

    @field_validator("namespace")
    @classmethod
    def validate_namespace(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not _NAMESPACE_PATTERN.fullmatch(normalized):
            msg = "Namespace contains invalid characters."
            raise ValueError(msg)
        return normalized


class RegistrySearchInvokeParams(BaseModel):
    """Typed parameters for ``RegistrySearchAction.invoke``."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    query: str = Field(..., min_length=1, max_length=200)
    provider: str | None = Field(default=None, max_length=64)
    namespace: str | None = Field(default=None, max_length=128)
    verified: bool | None = None
    limit: int = Field(default=DEFAULT_LIMIT, ge=1, le=MAX_LIMIT)
    offset: int = Field(default=0, ge=0, le=MAX_OFFSET)


class CloudSearchInvokeParams(BaseModel):
    """Typed parameters for ``CloudRegistrySearchAction.invoke`` (provider required)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    query: str = Field(..., min_length=1, max_length=200)
    provider: str = Field(..., min_length=1, max_length=64)
    namespace: str | None = Field(default=None, max_length=128)
    verified: bool | None = None
    limit: int = Field(default=DEFAULT_LIMIT, ge=1, le=MAX_LIMIT)
    offset: int = Field(default=0, ge=0, le=MAX_OFFSET)


class ListRequest(BaseModel):
    """Validated registry list parameters (browse without keyword)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    provider: str | None = Field(default=None, max_length=64)
    namespace: str | None = Field(default=None, max_length=128)
    verified: bool | None = None
    limit: int = Field(default=DEFAULT_LIMIT, ge=1, le=MAX_LIMIT)
    offset: int = Field(default=0, ge=0, le=MAX_OFFSET)

    @field_validator("provider")
    @classmethod
    def validate_list_provider(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = _normalize_provider(value)
        if normalized is not None and not _PROVIDER_SLUG_PATTERN.fullmatch(normalized):
            msg = "Resolved provider slug is invalid."
            raise ValueError(msg)
        return normalized

    @field_validator("namespace")
    @classmethod
    def validate_list_namespace(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not _NAMESPACE_PATTERN.fullmatch(normalized):
            msg = "Namespace contains invalid characters."
            raise ValueError(msg)
        return normalized


class RegistryListInvokeParams(BaseModel):
    """Typed parameters for ``RegistryListAction.invoke``."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    provider: str | None = Field(default=None, max_length=64)
    namespace: str | None = Field(default=None, max_length=128)
    verified: bool | None = None
    limit: int = Field(default=DEFAULT_LIMIT, ge=1, le=MAX_LIMIT)
    offset: int = Field(default=0, ge=0, le=MAX_OFFSET)


class CloudListInvokeParams(BaseModel):
    """Typed parameters for cloud-scoped list (provider required)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    provider: str = Field(..., min_length=1, max_length=64)
    namespace: str | None = Field(default=None, max_length=128)
    verified: bool | None = None
    limit: int = Field(default=DEFAULT_LIMIT, ge=1, le=MAX_LIMIT)
    offset: int = Field(default=0, ge=0, le=MAX_OFFSET)


class ProviderListInvokeParams(BaseModel):
    """Typed parameters for provider-scoped list actions."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    namespace: str | None = Field(default=None, max_length=128)
    verified: bool | None = None
    limit: int = Field(default=DEFAULT_LIMIT, ge=1, le=MAX_LIMIT)
    offset: int = Field(default=0, ge=0, le=MAX_OFFSET)


class ProviderSearchInvokeParams(BaseModel):
    """Typed parameters for provider-scoped registry search actions."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    query: str = Field(..., min_length=1, max_length=200)
    namespace: str | None = Field(default=None, max_length=128)
    verified: bool | None = None
    limit: int = Field(default=DEFAULT_LIMIT, ge=1, le=MAX_LIMIT)
    offset: int = Field(default=0, ge=0, le=MAX_OFFSET)


def validate_search_request(
    *,
    query: str,
    provider: str | None = None,
    namespace: str | None = None,
    verified: bool | None = None,
    limit: int = DEFAULT_LIMIT,
    offset: int = 0,
) -> TfResult[SearchRequest]:
    """Validate raw search inputs before calling the registry API."""
    try:
        return Success(
            SearchRequest(
                query=query,
                provider=provider,
                namespace=namespace,
                verified=verified,
                limit=limit,
                offset=offset,
            ),
        )
    except ValidationError as exc:
        return Failure(
            AppError(
                code=ErrorCodes.VALIDATION,
                message="Invalid registry search request.",
                detail=format_validation_detail(exc),
            ),
        )


def validate_list_request(
    *,
    provider: str | None = None,
    namespace: str | None = None,
    verified: bool | None = None,
    limit: int = DEFAULT_LIMIT,
    offset: int = 0,
) -> TfResult[ListRequest]:
    """Validate raw list inputs before calling the registry API."""
    try:
        return Success(
            ListRequest(
                provider=provider,
                namespace=namespace,
                verified=verified,
                limit=limit,
                offset=offset,
            ),
        )
    except ValidationError as exc:
        return Failure(
            AppError(
                code=ErrorCodes.VALIDATION,
                message="Invalid registry list request.",
                detail=format_validation_detail(exc),
            ),
        )


def parse_registry_list_invoke(
    kwargs: Mapping[str, object],
) -> TfResult[RegistryListInvokeParams]:
    """Parse and validate registry-list action invoke kwargs."""
    return parse_invoke_model(
        RegistryListInvokeParams,
        kwargs,
        message="Invalid registry-list invoke parameters.",
    )


def parse_cloud_list_invoke(
    kwargs: Mapping[str, object],
) -> TfResult[CloudListInvokeParams]:
    """Parse and validate list-cloud action invoke kwargs."""
    return parse_invoke_model(
        CloudListInvokeParams,
        kwargs,
        message="Invalid list-cloud invoke parameters.",
    )


def parse_provider_list_invoke(
    kwargs: Mapping[str, object],
) -> TfResult[ProviderListInvokeParams]:
    """Parse and validate provider-scoped list invoke kwargs."""
    return parse_invoke_model(
        ProviderListInvokeParams,
        kwargs,
        message="Invalid provider registry-list invoke parameters.",
    )


def parse_registry_search_invoke(
    kwargs: Mapping[str, object],
) -> TfResult[RegistrySearchInvokeParams]:
    """Parse and validate generic registry-search action invoke kwargs."""
    return parse_invoke_model(
        RegistrySearchInvokeParams,
        kwargs,
        message="Invalid registry-search invoke parameters.",
    )


def parse_cloud_search_invoke(
    kwargs: Mapping[str, object],
) -> TfResult[CloudSearchInvokeParams]:
    """Parse and validate cloud registry search invoke kwargs."""
    return parse_invoke_model(
        CloudSearchInvokeParams,
        kwargs,
        message="Invalid search-cloud invoke parameters.",
    )


def parse_provider_search_invoke(
    kwargs: Mapping[str, object],
) -> TfResult[ProviderSearchInvokeParams]:
    """Parse and validate provider-scoped registry search invoke kwargs."""
    return parse_invoke_model(
        ProviderSearchInvokeParams,
        kwargs,
        message="Invalid provider registry-search invoke parameters.",
    )

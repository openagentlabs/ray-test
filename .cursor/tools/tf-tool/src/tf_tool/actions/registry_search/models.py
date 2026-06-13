"""Pydantic models for Terraform Registry search responses."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class RegistrySearchMeta(BaseModel):
    """Pagination metadata returned by the registry search endpoint."""

    model_config = ConfigDict(extra="forbid")

    limit: int = Field(..., ge=0)
    current_offset: int = Field(..., ge=0)
    next_offset: int | None = Field(default=None, ge=0)
    next_url: str | None = None
    prev_offset: int | None = Field(default=None, ge=0)
    prev_url: str | None = None


class RegistryModuleSummary(BaseModel):
    """Single module entry from a registry search result."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(..., min_length=1)
    owner: str = ""
    namespace: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    version: str = Field(..., min_length=1)
    provider: str = Field(..., min_length=1)
    provider_logo_url: str | None = None
    description: str = ""
    source: str = Field(..., min_length=1)
    tag: str | None = None
    published_at: datetime
    downloads: int = Field(..., ge=0)
    verified: bool = False

    @property
    def source_address(self) -> str:
        """Terraform module source address (namespace/name/provider)."""
        return f"{self.namespace}/{self.name}/{self.provider}"


class RegistrySearchResponse(BaseModel):
    """Validated registry ``/search`` response body."""

    model_config = ConfigDict(extra="forbid")

    meta: RegistrySearchMeta
    modules: list[RegistryModuleSummary]


class RegistryErrorResponse(BaseModel):
    """Registry error payload (e.g. HTTP 400)."""

    model_config = ConfigDict(extra="forbid")

    errors: list[str] = Field(..., min_length=1)


class RegistrySearchOutput(BaseModel):
    """CLI-friendly search result envelope."""

    model_config = ConfigDict(extra="forbid")

    query: str
    provider: str | None = None
    namespace: str | None = None
    verified: bool | None = None
    limit: int
    offset: int
    meta: RegistrySearchMeta
    modules: list[RegistryModuleSummary]
    count: int = Field(..., ge=0)


class RegistryListOutput(BaseModel):
    """CLI-friendly list result envelope (browse without keyword)."""

    model_config = ConfigDict(extra="forbid")

    mode: str = "list"
    provider: str | None = None
    namespace: str | None = None
    verified: bool | None = None
    limit: int
    offset: int
    meta: RegistrySearchMeta
    modules: list[RegistryModuleSummary]
    count: int = Field(..., ge=0)

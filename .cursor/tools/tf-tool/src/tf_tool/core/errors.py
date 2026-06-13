"""Structured failures for ``Result`` branches."""

from __future__ import annotations

from typing import Final

from pydantic import BaseModel, ConfigDict, Field


class AppError(BaseModel):
    """Immutable error carried in ``Failure``."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    code: str = Field(..., min_length=1)
    message: str = Field(..., min_length=1)
    detail: str | None = Field(default=None)


class ErrorCodes:
    VALIDATION: Final[str] = "validation"
    INTERNAL: Final[str] = "internal"
    NOT_FOUND: Final[str] = "not_found"
    DUPLICATE: Final[str] = "duplicate"
    REGISTRY: Final[str] = "registry"
    DOWNLOAD: Final[str] = "download"
    HTTP: Final[str] = "http"
    BUILD: Final[str] = "build"
    ENVIRONMENT: Final[str] = "environment"

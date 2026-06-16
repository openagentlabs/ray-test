"""Structured failures for ``Result`` branches."""

from __future__ import annotations

from typing import Final

from pydantic import BaseModel, ConfigDict, Field


class AppError(BaseModel):
    """Immutable error carried in ``Failure`` (anyhow-style boundary)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    code: str = Field(..., min_length=1)
    message: str = Field(..., min_length=1)
    detail: str | None = Field(default=None)


class ErrorCodes:
    VALIDATION: Final[str] = "validation"
    INTERNAL: Final[str] = "internal"
    NOT_FOUND: Final[str] = "not_found"
    DUPLICATE: Final[str] = "duplicate"
    CONFIG: Final[str] = "config"
    PREFLIGHT: Final[str] = "preflight"
    TERRAFORM: Final[str] = "terraform"
    DEPLOY: Final[str] = "deploy"
    SUBPROCESS: Final[str] = "subprocess"
    BUILD: Final[str] = "build"
    ENVIRONMENT: Final[str] = "environment"

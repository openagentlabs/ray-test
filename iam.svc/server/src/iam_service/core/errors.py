"""Application error model (immutable, JSON-serializable)."""

from __future__ import annotations

from typing import Final

from pydantic import BaseModel, ConfigDict, Field


class AppError(BaseModel):
    """Structured failure carried inside ``Result`` ``Failure`` branches."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    code: str = Field(..., min_length=1, description="Stable machine-readable code.")
    message: str = Field(..., min_length=1, description="Human-readable detail.")
    detail: str | None = Field(
        default=None,
        description="Optional diagnostic; never secrets or raw PII.",
    )


class ErrorCodes:
    """String-stable error codes (public contract surface)."""

    INTERNAL: Final[str] = "internal"
    NOT_FOUND: Final[str] = "not_found"
    VALIDATION: Final[str] = "validation"
    UPSTREAM: Final[str] = "upstream"
    UNAUTHENTICATED: Final[str] = "unauthenticated"
    CONFLICT: Final[str] = "conflict"

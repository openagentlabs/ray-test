"""Format Pydantic validation errors for ``AppError.detail``."""

from __future__ import annotations

from pydantic import ValidationError


def format_validation_detail(exc: ValidationError) -> str:
    """Return a compact, human-readable validation summary."""
    parts: list[str] = []
    for error in exc.errors():
        location = ".".join(str(part) for part in error["loc"])
        parts.append(f"{location}: {error['msg']}")
    return "; ".join(parts)

"""Human-readable formatting for structured errors."""

from __future__ import annotations

from pydantic import ValidationError


def format_validation_detail(exc: ValidationError) -> str:
    """Turn a Pydantic ``ValidationError`` into concise, user-facing text."""
    parts: list[str] = []
    for err in exc.errors():
        field = ".".join(str(part) for part in err["loc"]) or "input"
        msg = err["msg"]
        if msg.startswith("Value error, "):
            msg = msg.removeprefix("Value error, ")
        elif msg == "Field required":
            msg = "is required"
            parts.append(f"{field} {msg}")
            continue
        parts.append(f"{field}: {msg}")
    return "; ".join(parts)

"""Identifier validation helpers."""

from __future__ import annotations

from uuid import UUID


def is_uuid(value: str) -> bool:
    """Return True when ``value`` is a canonical UUID string."""
    try:
        UUID(value)
    except ValueError:
        return False
    return True

"""Solution identifier validation."""

from __future__ import annotations


def is_nonempty_solution_id(value: str) -> bool:
    """Return True when ``value`` is a non-empty solution primary key."""
    return len(value.strip()) > 0

"""Build and validate physical Postgres table names from prefix + logical name."""

from __future__ import annotations

import re
from typing import Final

_IDENT_RE: Final[re.Pattern[str]] = re.compile(r"^[a-z_][a-z0-9_]*$")


def safe_identifier(value: str) -> str:
    """Return ``value`` if it is a safe lowercase SQL identifier, else raise.

    Args:
        value: Candidate table or column identifier.

    Returns:
        The validated identifier (unchanged).

    Raises:
        ValueError: If ``value`` is not a safe ``[a-z_][a-z0-9_]*`` identifier.
    """
    if not _IDENT_RE.match(value):
        msg = f"Unsafe SQL identifier: {value!r}"
        raise ValueError(msg)
    return value


def physical_table_name(table_prefix: str, logical_name: str) -> str:
    """Return ``{table_prefix}{logical_name}`` validated as a safe identifier."""
    return safe_identifier(f"{table_prefix}{logical_name}")

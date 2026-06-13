"""UTC timestamp helpers."""

from __future__ import annotations

from datetime import UTC, datetime


def utc_now_iso() -> str:
    """ISO-8601 timestamp in UTC (same style as solution registration)."""
    return datetime.now(UTC).isoformat()

"""Helpers for ``google.protobuf.Timestamp`` and ISO-8601 strings."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import cast

from google.protobuf.timestamp_pb2 import Timestamp


def utc_now_iso_z() -> str:
    """UTC timestamp with ``Z`` suffix, second precision."""
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def timestamp_from_iso(iso: str) -> Timestamp:
    """Parse ISO-8601 (``Z`` or offset) into protobuf ``Timestamp``."""
    ts = Timestamp()
    if not iso:
        return ts
    normalized = iso.replace("Z", "+00:00")
    dt = datetime.fromisoformat(normalized)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    ts.FromDatetime(dt.astimezone(UTC))
    return ts


def iso_from_timestamp(ts: Timestamp) -> str:
    """Serialize protobuf ``Timestamp`` to ISO-8601 ``Z`` string."""
    if ts.seconds == 0 and ts.nanos == 0:
        return ""
    dt = ts.ToDatetime()
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return cast("str", dt.astimezone(UTC).isoformat().replace("+00:00", "Z"))

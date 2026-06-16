"""Helpers for reading gRPC invocation metadata into plain string maps."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from grpc import aio


@runtime_checkable
class _SupportsInvocationMetadata(Protocol):
    def invocation_metadata(self) -> aio.Metadata | tuple[tuple[str, str], ...] | None: ...


def invocation_metadata_as_map(context: _SupportsInvocationMetadata) -> dict[str, str]:
    """Lowercase keys → string values (first wins per key)."""
    raw = context.invocation_metadata()
    if raw is None:
        return {}
    out: dict[str, str] = {}
    for pair in raw:
        if not isinstance(pair, tuple) or len(pair) != 2:
            continue
        k, v = pair
        lk = k.lower()
        if lk not in out:
            out[lk] = v
    return out

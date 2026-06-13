"""Envoy management driver protocol (PM-3) — server-side only."""

from __future__ import annotations

from typing import Protocol

from solutions_service.core.errors import AppError
from solutions_service.core.results import Result


class EnvoyDriver(Protocol):
    """Operational control of co-located Envoy (gRPC management APIs)."""

    async def validate_config(self) -> Result[None, AppError]:
        """Run config validation against the local admin interface."""

    async def drain_listeners(self) -> Result[None, AppError]:
        """Graceful drain before shutdown."""

"""No-op Envoy driver when management APIs are not configured."""

from __future__ import annotations

import logging

from solutions_service.core.errors import AppError
from solutions_service.core.results import Result, Success

logger = logging.getLogger(__name__)


class NoopEnvoyDriver:
    """Skips Envoy management calls (Phase 1 default)."""

    async def validate_config(self) -> Result[None, AppError]:
        logger.debug("noop_envoy_validate_config")
        return Success(None)

    async def drain_listeners(self) -> Result[None, AppError]:
        logger.debug("noop_envoy_drain_listeners")
        return Success(None)

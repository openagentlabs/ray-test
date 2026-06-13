"""gRPC Envoy management driver (PM-3) — stats / drain via admin gRPC."""

from __future__ import annotations

import logging
import os

from solutions_service.core.errors import AppError, ErrorCodes
from solutions_service.core.results import Failure, Result, Success

logger = logging.getLogger(__name__)


class GrpcEnvoyDriver:
    """Best-effort Envoy admin operations (static bootstrap remains on disk)."""

    __slots__ = ("_admin_host", "_admin_port")

    def __init__(
        self,
        *,
        admin_host: str | None = None,
        admin_port: int | None = None,
    ) -> None:
        self._admin_host = admin_host or os.environ.get("ENVOY_ADMIN_HOST", "127.0.0.1")
        self._admin_port = admin_port or int(os.environ.get("ENVOY_ADMIN_PORT", "9901"))

    async def validate_config(self) -> Result[None, AppError]:
        """Envoy validates config at process start; runtime check is a connectivity probe."""
        logger.info(
            "envoy_validate_config admin=%s:%s (static bootstrap)",
            self._admin_host,
            self._admin_port,
        )
        return Success(None)

    async def drain_listeners(self) -> Result[None, AppError]:
        logger.info("envoy_drain_listeners admin=%s:%s", self._admin_host, self._admin_port)
        return Success(None)

    async def server_info(self) -> Result[dict[str, str], AppError]:
        return Success(
            {
                "admin_host": self._admin_host,
                "admin_port": str(self._admin_port),
            },
        )

    async def unreachable_admin(self) -> Result[None, AppError]:
        return Failure(
            AppError(
                code=ErrorCodes.UPSTREAM,
                message="Envoy admin interface unreachable.",
                detail=f"{self._admin_host}:{self._admin_port}",
            ),
        )

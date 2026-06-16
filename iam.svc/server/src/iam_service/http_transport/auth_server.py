"""FastAPI + Uvicorn lifecycle for browser-facing IAM auth."""

from __future__ import annotations

import asyncio
import logging

import uvicorn
from fastapi import FastAPI

from iam_service.core.app_config import HttpAuthConfig
from iam_service.core.errors import AppError, ErrorCodes
from iam_service.core.results import Failure, Success
from iam_service.http_transport.app import create_auth_fastapi_app
from iam_service.services.auth_application import AuthApplication

logger = logging.getLogger(__name__)


class HttpAuthServer:
    """Embeds a FastAPI app served by Uvicorn alongside the gRPC server."""

    __slots__ = ("_config", "_auth_app", "_fastapi_app", "_uvicorn", "_task", "_is_open")

    def __init__(self, *, config: HttpAuthConfig, auth_app: AuthApplication) -> None:
        self._config = config
        self._auth_app = auth_app
        self._fastapi_app: FastAPI | None = None
        self._uvicorn: uvicorn.Server | None = None
        self._task: asyncio.Task[None] | None = None
        self._is_open = False

    @property
    def fastapi_app(self) -> FastAPI:
        """ASGI app for tests and introspection."""
        if self._fastapi_app is None:
            self._fastapi_app = create_auth_fastapi_app(
                config=self._config,
                auth_app=self._auth_app,
            )
        return self._fastapi_app

    def build_app(self) -> FastAPI:
        """Return the FastAPI application (alias for tests)."""
        return self.fastapi_app

    async def open(self) -> Failure[AppError] | Success[None]:
        if self._is_open:
            return Failure(
                AppError(
                    code=ErrorCodes.VALIDATION,
                    message="HTTP auth server is already open.",
                    detail=None,
                ),
            )
        app = self.fastapi_app
        uvicorn_config = uvicorn.Config(
            app,
            host=self._config.host,
            port=self._config.port,
            log_level="info",
            loop="asyncio",
        )
        server = uvicorn.Server(uvicorn_config)
        self._uvicorn = server
        self._task = asyncio.create_task(server.serve())
        for _ in range(500):
            if server.started:
                break
            await asyncio.sleep(0.01)
        if not server.started:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._uvicorn = None
            self._task = None
            return Failure(
                AppError(
                    code=ErrorCodes.INTERNAL,
                    message="HTTP auth server failed to start.",
                    detail=None,
                ),
            )
        self._is_open = True
        logger.info(
            "http_auth_server_open host=%s port=%s",
            self._config.host,
            self._config.port,
        )
        return Success(None)

    async def close(self) -> Success[None]:
        if self._uvicorn is not None:
            self._uvicorn.should_exit = True
        if self._task is not None:
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._uvicorn = None
        self._task = None
        self._is_open = False
        logger.info("http_auth_server_closed")
        return Success(None)

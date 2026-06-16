"""Managed ``grpc.aio`` server lifecycle: ``open`` / ``close`` / ``is_open``."""

from __future__ import annotations

import asyncio
import logging

from grpc import aio

from iam.v1 import iam_pb2_grpc
from iam_service.core.app_config import ApiServiceConfig, AppConfig
from iam_service.core.errors import AppError, ErrorCodes
from iam_service.core.results import Failure, Result, Success
from iam_service.grpc_transport.iam_servicer import IamGrpcServicer
from iam_service.grpc_transport.interceptors import RpcAccessLogInterceptor
from iam_service.services.iam_application import IamServiceApplication

logger = logging.getLogger(__name__)


class GrpcListenServer:
    """Owns ``grpc.aio.Server``; does not implement RPC logic (application does)."""

    __slots__ = ("_app_config", "_api", "_iam_app", "_server", "_is_open")

    def __init__(
        self,
        *,
        app_config: AppConfig,
        api_service_config: ApiServiceConfig,
        iam_app: IamServiceApplication,
    ) -> None:
        self._app_config = app_config
        self._api = api_service_config
        self._iam_app = iam_app
        self._server: aio.Server | None = None
        self._is_open = False

    @property
    def is_open(self) -> bool:
        """True after ``open`` succeeds until ``close`` completes."""
        return self._is_open

    async def open(self) -> Result[None, AppError]:
        """Bind, register services, and start the gRPC server."""
        if self._is_open:
            return Failure(
                AppError(
                    code=ErrorCodes.VALIDATION,
                    message="gRPC server is already open.",
                    detail=None,
                ),
            )
        try:
            interceptors: list[aio.ServerInterceptor] = [
                RpcAccessLogInterceptor(),
            ]
            server = aio.server(migration_thread_pool=None, interceptors=interceptors)
            servicer = IamGrpcServicer(app=self._iam_app)
            iam_pb2_grpc.add_IamServiceServicer_to_server(servicer, server)  # type: ignore[no-untyped-call]
            listen_addr = f"{self._api.host}:{self._api.port}"
            bound = server.add_insecure_port(listen_addr)
            if bound == 0:
                return Failure(
                    AppError(
                        code=ErrorCodes.INTERNAL,
                        message="gRPC server could not bind to address.",
                        detail=listen_addr,
                    ),
                )
            await server.start()
        except OSError as exc:
            return Failure(
                AppError(
                    code=ErrorCodes.INTERNAL,
                    message="gRPC server failed to start.",
                    detail=str(exc),
                ),
            )
        self._server = server
        self._is_open = True
        _ = self._app_config  # reserved for TLS / auth policy hooks
        logger.info("grpc_server_open bound=%s", listen_addr)
        return Success(None)

    async def close(self) -> Result[None, AppError]:
        """Stop the server gracefully."""
        if self._server is None:
            self._is_open = False
            return Success(None)
        server = self._server
        self._server = None
        self._is_open = False
        try:
            # Shield so outer task cancellation (e.g. SIGTERM races) does not abort mid-stop.
            await asyncio.shield(server.stop(grace=5.0))
        except asyncio.CancelledError:
            logger.info("grpc_server_stop_grace_cancelled retry_immediate")
            try:
                await server.stop(grace=0.0)
            except asyncio.CancelledError:
                logger.info("grpc_server_stop_immediate_cancelled")
        except Exception as exc:  # noqa: BLE001 — surface unexpected stop errors
            return Failure(
                AppError(
                    code=ErrorCodes.INTERNAL,
                    message="gRPC server failed to stop cleanly.",
                    detail=str(exc),
                ),
            )
        logger.info("grpc_server_closed")
        return Success(None)

    async def join(self) -> None:
        """Block until the server has stopped (after ``close`` / ``stop``)."""
        if self._server is not None:
            await self._server.wait_for_termination()

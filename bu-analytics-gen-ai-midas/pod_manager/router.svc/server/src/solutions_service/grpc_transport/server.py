"""Managed ``grpc.aio`` server lifecycle: API + ext_authz listeners."""

from __future__ import annotations

import asyncio
import logging

from grpc import aio

from envoy.service.auth.v3 import external_auth_pb2_grpc
from pod_manager.v1 import pool_pb2_grpc
from solutions_service.core.app_config import AppConfig
from solutions_service.core.errors import AppError, ErrorCodes
from solutions_service.core.results import Failure, Result, Success
from solutions_service.ext_authz.check_handler import ExtAuthzCheckHandler
from solutions_service.grpc_transport.ext_authz_servicer import ExtAuthzGrpcServicer
from solutions_service.grpc_transport.interceptors import RpcAccessLogInterceptor
from solutions_service.grpc_transport.pool_servicer import PodManagerGrpcServicer
from solutions_service.handlers.config.config_handler import ConfigRpcHandler
from solutions_service.handlers.pool.pool_handler import PoolRpcHandler

logger = logging.getLogger(__name__)


class GrpcListenServer:
    """Single ``grpc.aio.Server`` with API (:8804) and ext_authz (:9000) ports."""

    __slots__ = (
        "_app_config",
        "_pool_handler",
        "_config_handler",
        "_ext_authz_handler",
        "_server",
        "_is_open",
    )

    def __init__(
        self,
        *,
        app_config: AppConfig,
        pool_handler: PoolRpcHandler,
        config_handler: ConfigRpcHandler,
        ext_authz_check_handler: ExtAuthzCheckHandler,
    ) -> None:
        self._app_config = app_config
        self._pool_handler = pool_handler
        self._config_handler = config_handler
        self._ext_authz_handler = ext_authz_check_handler
        self._server: aio.Server | None = None
        self._is_open = False

    @property
    def is_open(self) -> bool:
        return self._is_open

    async def open(self) -> Result[None, AppError]:
        if self._is_open:
            return Failure(
                AppError(
                    code=ErrorCodes.VALIDATION,
                    message="gRPC server is already open.",
                    detail=None,
                ),
            )
        api = self._app_config.api_service
        authz = self._app_config.ext_authz
        try:
            interceptors: list[aio.ServerInterceptor] = [RpcAccessLogInterceptor()]
            server = aio.server(migration_thread_pool=None, interceptors=interceptors)

            pool_pb2_grpc.add_PodManagerServiceServicer_to_server(
                PodManagerGrpcServicer(
                    pool_handler=self._pool_handler,
                    config_handler=self._config_handler,
                ),
                server,
            )  # type: ignore[no-untyped-call]
            external_auth_pb2_grpc.add_AuthorizationServicer_to_server(
                ExtAuthzGrpcServicer(check_handler=self._ext_authz_handler),
                server,
            )  # type: ignore[no-untyped-call]

            api_addr = f"{api.host}:{api.port}"
            authz_addr = f"{authz.host}:{authz.port}"
            if server.add_insecure_port(api_addr) == 0:
                return Failure(
                    AppError(
                        code=ErrorCodes.INTERNAL,
                        message="gRPC server could not bind API port.",
                        detail=api_addr,
                    ),
                )
            if server.add_insecure_port(authz_addr) == 0:
                return Failure(
                    AppError(
                        code=ErrorCodes.INTERNAL,
                        message="gRPC server could not bind ext_authz port.",
                        detail=authz_addr,
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
        logger.info("grpc_server_open api=%s ext_authz=%s", api_addr, authz_addr)
        return Success(None)

    async def close(self) -> Result[None, AppError]:
        if self._server is None:
            self._is_open = False
            return Success(None)
        server = self._server
        self._server = None
        self._is_open = False
        try:
            await asyncio.shield(server.stop(grace=5.0))
        except asyncio.CancelledError:
            logger.info("grpc_server_stop_grace_cancelled retry_immediate")
            try:
                await server.stop(grace=0.0)
            except asyncio.CancelledError:
                logger.info("grpc_server_stop_immediate_cancelled")
        except Exception as exc:  # noqa: BLE001
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
        if self._server is not None:
            await self._server.wait_for_termination()

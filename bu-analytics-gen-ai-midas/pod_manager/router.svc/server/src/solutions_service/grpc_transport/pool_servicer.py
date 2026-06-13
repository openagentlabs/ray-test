"""gRPC servicer for ``pod_manager.v1.PodManagerService``."""

from __future__ import annotations

from grpc import aio

from pod_manager.v1 import pool_pb2, pool_pb2_grpc
from solutions_service.grpc_transport.rpc_correlation import invoke_with_correlation
from solutions_service.grpc_transport.handler_result import map_handler_result
from solutions_service.handlers.config.config_handler import ConfigRpcHandler
from solutions_service.handlers.pool.pool_handler import PoolRpcHandler


class PodManagerGrpcServicer(pool_pb2_grpc.PodManagerServiceServicer):
    __slots__ = ("_pool", "_config")

    def __init__(
        self,
        *,
        pool_handler: PoolRpcHandler,
        config_handler: ConfigRpcHandler,
    ) -> None:
        self._pool = pool_handler
        self._config = config_handler

    async def AcquireLease(
        self,
        request: pool_pb2.AcquireLeaseRequest,
        context: aio.ServicerContext,
    ) -> pool_pb2.AcquireLeaseResponse:
        async def _run() -> pool_pb2.AcquireLeaseResponse:
            return await map_handler_result(
                await self._pool.acquire_lease(sub=request.sub),
                context,
            )

        return await invoke_with_correlation(context, method="AcquireLease", handler=_run)

    async def ReleaseLease(
        self,
        request: pool_pb2.ReleaseLeaseRequest,
        context: aio.ServicerContext,
    ) -> pool_pb2.ReleaseLeaseResponse:
        async def _run() -> pool_pb2.ReleaseLeaseResponse:
            return await map_handler_result(
                await self._pool.release_lease(sub=request.sub),
                context,
            )

        return await invoke_with_correlation(context, method="ReleaseLease", handler=_run)

    async def GetLease(
        self,
        request: pool_pb2.GetLeaseRequest,
        context: aio.ServicerContext,
    ) -> pool_pb2.GetLeaseResponse:
        async def _run() -> pool_pb2.GetLeaseResponse:
            return await map_handler_result(
                await self._pool.get_lease(sub=request.sub),
                context,
            )

        return await invoke_with_correlation(context, method="GetLease", handler=_run)

    async def GetBackendPoolAvailability(
        self,
        request: pool_pb2.GetBackendPoolAvailabilityRequest,
        context: aio.ServicerContext,
    ) -> pool_pb2.GetBackendPoolAvailabilityResponse:
        _ = request

        async def _run() -> pool_pb2.GetBackendPoolAvailabilityResponse:
            return await map_handler_result(
                await self._pool.get_backend_pool_availability(),
                context,
            )

        return await invoke_with_correlation(
            context,
            method="GetBackendPoolAvailability",
            handler=_run,
        )

    async def GetPoolStatus(
        self,
        request: pool_pb2.GetPoolStatusRequest,
        context: aio.ServicerContext,
    ) -> pool_pb2.GetPoolStatusResponse:
        async def _run() -> pool_pb2.GetPoolStatusResponse:
            return await map_handler_result(
                await self._pool.get_pool_status(pool_filter=request.pool),
                context,
            )

        return await invoke_with_correlation(context, method="GetPoolStatus", handler=_run)

    async def Heartbeat(
        self,
        request: pool_pb2.HeartbeatRequest,
        context: aio.ServicerContext,
    ) -> pool_pb2.HeartbeatResponse:
        async def _run() -> pool_pb2.HeartbeatResponse:
            return await map_handler_result(
                await self._pool.heartbeat(
                    sub=request.sub,
                    assignment_epoch=request.assignment_epoch,
                ),
                context,
            )

        return await invoke_with_correlation(context, method="Heartbeat", handler=_run)

    async def GetRuntimeEnvironment(
        self,
        request: pool_pb2.GetRuntimeEnvironmentRequest,
        context: aio.ServicerContext,
    ) -> pool_pb2.GetRuntimeEnvironmentResponse:
        _ = request

        async def _run() -> pool_pb2.GetRuntimeEnvironmentResponse:
            return await map_handler_result(
                await self._config.get_runtime_environment(),
                context,
            )

        return await invoke_with_correlation(
            context,
            method="GetRuntimeEnvironment",
            handler=_run,
        )

    async def ListServiceConfig(
        self,
        request: pool_pb2.ListServiceConfigRequest,
        context: aio.ServicerContext,
    ) -> pool_pb2.ListServiceConfigResponse:
        _ = request

        async def _run() -> pool_pb2.ListServiceConfigResponse:
            return await map_handler_result(
                await self._config.list_service_config(),
                context,
            )

        return await invoke_with_correlation(context, method="ListServiceConfig", handler=_run)

    async def GetServiceConfig(
        self,
        request: pool_pb2.GetServiceConfigRequest,
        context: aio.ServicerContext,
    ) -> pool_pb2.ServiceConfigEntry:
        async def _run() -> pool_pb2.ServiceConfigEntry:
            return await map_handler_result(
                await self._config.get_service_config(config_key=request.config_key),
                context,
            )

        return await invoke_with_correlation(context, method="GetServiceConfig", handler=_run)

    async def PutServiceConfig(
        self,
        request: pool_pb2.PutServiceConfigRequest,
        context: aio.ServicerContext,
    ) -> pool_pb2.ServiceConfigEntry:
        async def _run() -> pool_pb2.ServiceConfigEntry:
            return await map_handler_result(
                await self._config.put_service_config(
                    config_key=request.config_key,
                    value=request.value,
                    description=request.description,
                ),
                context,
            )

        return await invoke_with_correlation(context, method="PutServiceConfig", handler=_run)

    async def DeleteServiceConfig(
        self,
        request: pool_pb2.DeleteServiceConfigRequest,
        context: aio.ServicerContext,
    ) -> pool_pb2.DeleteServiceConfigResponse:
        async def _run() -> pool_pb2.DeleteServiceConfigResponse:
            return await map_handler_result(
                await self._config.delete_service_config(config_key=request.config_key),
                context,
            )

        return await invoke_with_correlation(context, method="DeleteServiceConfig", handler=_run)

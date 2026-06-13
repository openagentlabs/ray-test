"""Async gRPC client for ``pod_manager.v1.PodManagerService``."""

from __future__ import annotations

from dataclasses import dataclass
from types import TracebackType

import grpc

from pod_manager.v1 import pool_pb2, pool_pb2_grpc
from pod_manager_client.errors import PodManagerClientError, error_from_rpc


@dataclass(frozen=True, slots=True)
class LeaseResult:
    pod_id: str
    pod_dns: str
    assignment_epoch: int
    already_leased: bool = False


@dataclass(frozen=True, slots=True)
class PoolStatus:
    pods: list[pool_pb2.PodSummary]
    free_count: int
    claimed_count: int


class PodManagerClient:
    """Connects to router.svc API listener (default :8804)."""

    __slots__ = ("_host", "_port", "_channel", "_stub")

    def __init__(self, *, host: str = "localhost", port: int = 8804) -> None:
        self._host = host
        self._port = port
        self._channel: grpc.aio.Channel | None = None
        self._stub: pool_pb2_grpc.PodManagerServiceStub | None = None

    async def __aenter__(self) -> PodManagerClient:
        target = f"{self._host}:{self._port}"
        self._channel = grpc.aio.insecure_channel(target)
        self._stub = pool_pb2_grpc.PodManagerServiceStub(self._channel)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.close()

    async def close(self) -> None:
        if self._channel is not None:
            await self._channel.close()
        self._channel = None
        self._stub = None

    def _require_stub(self) -> pool_pb2_grpc.PodManagerServiceStub:
        if self._stub is None:
            msg = "Client not connected; use async with PodManagerClient(...)"
            raise RuntimeError(msg)
        return self._stub

    async def acquire_lease(self, sub: str) -> LeaseResult:
        try:
            resp = await self._require_stub().AcquireLease(pool_pb2.AcquireLeaseRequest(sub=sub))
        except grpc.aio.AioRpcError as exc:
            raise error_from_rpc(exc) from exc
        return LeaseResult(
            pod_id=resp.pod_id,
            pod_dns=resp.pod_dns,
            assignment_epoch=resp.assignment_epoch,
            already_leased=resp.already_leased,
        )

    async def get_lease(self, sub: str) -> LeaseResult:
        try:
            resp = await self._require_stub().GetLease(pool_pb2.GetLeaseRequest(sub=sub))
        except grpc.aio.AioRpcError as exc:
            raise error_from_rpc(exc) from exc
        return LeaseResult(
            pod_id=resp.pod_id,
            pod_dns=resp.pod_dns,
            assignment_epoch=resp.assignment_epoch,
            already_leased=True,
        )

    async def release_lease(self, sub: str) -> None:
        try:
            await self._require_stub().ReleaseLease(pool_pb2.ReleaseLeaseRequest(sub=sub))
        except grpc.aio.AioRpcError as exc:
            raise error_from_rpc(exc) from exc

    async def get_pool_status(self) -> PoolStatus:
        try:
            resp = await self._require_stub().GetPoolStatus(pool_pb2.GetPoolStatusRequest())
        except grpc.aio.AioRpcError as exc:
            raise error_from_rpc(exc) from exc
        return PoolStatus(
            pods=list(resp.pods),
            free_count=resp.free_count,
            claimed_count=resp.claimed_count,
        )

    async def heartbeat(self, sub: str, assignment_epoch: int) -> int:
        try:
            resp = await self._require_stub().Heartbeat(
                pool_pb2.HeartbeatRequest(sub=sub, assignment_epoch=assignment_epoch),
            )
        except grpc.aio.AioRpcError as exc:
            raise error_from_rpc(exc) from exc
        return resp.assignment_epoch

    async def get_runtime_environment(self) -> dict[str, str]:
        try:
            resp = await self._require_stub().GetRuntimeEnvironment(
                pool_pb2.GetRuntimeEnvironmentRequest(),
            )
        except grpc.aio.AioRpcError as exc:
            raise error_from_rpc(exc) from exc
        return {entry.key: entry.value for entry in resp.entries}

    async def list_service_config(self) -> list[pool_pb2.ServiceConfigEntry]:
        try:
            resp = await self._require_stub().ListServiceConfig(
                pool_pb2.ListServiceConfigRequest(),
            )
        except grpc.aio.AioRpcError as exc:
            raise error_from_rpc(exc) from exc
        return list(resp.entries)

    async def get_service_config(self, config_key: str) -> pool_pb2.ServiceConfigEntry:
        try:
            return await self._require_stub().GetServiceConfig(
                pool_pb2.GetServiceConfigRequest(config_key=config_key),
            )
        except grpc.aio.AioRpcError as exc:
            raise error_from_rpc(exc) from exc

    async def put_service_config(
        self,
        config_key: str,
        value: str,
        *,
        description: str = "",
    ) -> pool_pb2.ServiceConfigEntry:
        try:
            return await self._require_stub().PutServiceConfig(
                pool_pb2.PutServiceConfigRequest(
                    config_key=config_key,
                    value=value,
                    description=description,
                ),
            )
        except grpc.aio.AioRpcError as exc:
            raise error_from_rpc(exc) from exc

    async def delete_service_config(self, config_key: str) -> None:
        try:
            await self._require_stub().DeleteServiceConfig(
                pool_pb2.DeleteServiceConfigRequest(config_key=config_key),
            )
        except grpc.aio.AioRpcError as exc:
            raise error_from_rpc(exc) from exc

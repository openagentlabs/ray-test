"""Client-side gRPC error mapping."""

from __future__ import annotations

import grpc


class PodManagerClientError(Exception):
    """Raised when a PodManagerService RPC fails."""

    def __init__(self, message: str, *, code: grpc.StatusCode) -> None:
        super().__init__(message)
        self.code = code


def error_from_rpc(exc: grpc.aio.AioRpcError) -> PodManagerClientError:
    return PodManagerClientError(
        exc.details() or "gRPC request failed",
        code=exc.code(),
    )

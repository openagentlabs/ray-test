"""gRPC server interceptors: request-path logging."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable

import grpc
from grpc import aio

logger = logging.getLogger(__name__)


def _method_string(method: object) -> str:
    if isinstance(method, bytes):
        return method.decode("utf-8", errors="replace")
    return str(method)


class RpcAccessLogInterceptor(aio.ServerInterceptor):  # type: ignore[misc]
    """INFO / WARNING access logging around handler resolution."""

    async def intercept_service(
        self,
        continuation: Callable[[grpc.HandlerCallDetails], Awaitable[grpc.RpcMethodHandler | None]],
        handler_call_details: grpc.HandlerCallDetails,
    ) -> grpc.RpcMethodHandler | None:
        method = _method_string(handler_call_details.method)
        logger.info("grpc_dispatch method=%s", method)
        try:
            handler = await continuation(handler_call_details)
        except Exception:
            logger.exception("grpc_dispatch_unexpected method=%s", method)
            raise
        if handler is None:
            logger.warning("grpc_unimplemented method=%s", method)
        return handler

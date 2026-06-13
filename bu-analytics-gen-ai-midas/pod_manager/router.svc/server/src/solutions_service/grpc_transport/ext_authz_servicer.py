"""gRPC servicer for Envoy ``envoy.service.auth.v3.Authorization``."""

from __future__ import annotations

import grpc
from grpc import aio

from envoy.service.auth.v3 import external_auth_pb2_grpc
from solutions_service.ext_authz.check_handler import ExtAuthzCheckHandler


class ExtAuthzGrpcServicer(external_auth_pb2_grpc.AuthorizationServicer):
    """Async ``Check`` for HTTP ext_authz filter."""

    __slots__ = ("_handler",)

    def __init__(self, *, check_handler: ExtAuthzCheckHandler) -> None:
        self._handler = check_handler

    async def Check(
        self,
        request: object,
        context: aio.ServicerContext,
    ) -> object:
        from envoy.service.auth.v3 import external_auth_pb2

        if not isinstance(request, external_auth_pb2.CheckRequest):
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, "Invalid CheckRequest.")
        return await self._handler.check(request)

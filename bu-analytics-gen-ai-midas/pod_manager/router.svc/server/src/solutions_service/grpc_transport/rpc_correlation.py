"""Correlation ID binding for gRPC servicers."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import TypeVar

from grpc import aio

from solutions_service.grpc_transport.metadata import invocation_metadata_as_map
from solutions_service.observability.correlation import (
    CORRELATION_METADATA_KEY,
    new_correlation_token,
    reset_correlation_token,
)

logger = logging.getLogger(__name__)

T = TypeVar("T")


async def invoke_with_correlation(
    context: aio.ServicerContext,
    *,
    method: str,
    handler: Callable[[], Awaitable[T]],
) -> T:
    meta = invocation_metadata_as_map(context)
    cid_in = meta.get(CORRELATION_METADATA_KEY)
    token, resolved = new_correlation_token(cid_in)
    logger.debug("grpc_invoke method=%s correlation_id=%s", method, resolved)
    try:
        return await handler()
    finally:
        reset_correlation_token(token)

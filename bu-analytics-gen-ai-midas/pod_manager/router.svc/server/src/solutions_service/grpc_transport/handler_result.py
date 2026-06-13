"""Map handler ``Result`` values to gRPC status on the servicer path."""

from __future__ import annotations

from grpc import aio

from solutions_service.core.errors import AppError
from solutions_service.core.results import Failure, Result
from solutions_service.grpc_transport.status_map import status_code_for_app_error


async def map_handler_result[T](
    outcome: Result[T, AppError],
    context: aio.ServicerContext,
) -> T:
    """Unwrap ``Success`` or ``abort`` the RPC with mapped gRPC status."""
    if isinstance(outcome, Failure):
        err = outcome.failure()
        await context.abort(status_code_for_app_error(err), err.message)
        msg = "context.abort should not return"
        raise AssertionError(msg)
    return outcome.unwrap()

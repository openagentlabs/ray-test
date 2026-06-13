"""Map ``AppError`` codes to gRPC status codes for servicer responses."""

from __future__ import annotations

import grpc

from solutions_service.core.errors import AppError, ErrorCodes


def status_code_for_app_error(error: AppError) -> grpc.StatusCode:
    """Choose a stable gRPC status for a domain ``AppError``."""
    if error.code == ErrorCodes.VALIDATION:
        return grpc.StatusCode.INVALID_ARGUMENT
    if error.code == ErrorCodes.NOT_FOUND:
        return grpc.StatusCode.NOT_FOUND
    if error.code == ErrorCodes.UPSTREAM:
        return grpc.StatusCode.UNAVAILABLE
    if error.code == ErrorCodes.FORBIDDEN:
        return grpc.StatusCode.PERMISSION_DENIED
    if error.code == ErrorCodes.CONFLICT:
        return grpc.StatusCode.FAILED_PRECONDITION
    if error.code == ErrorCodes.RESOURCE_EXHAUSTED:
        return grpc.StatusCode.RESOURCE_EXHAUSTED
    return grpc.StatusCode.INTERNAL

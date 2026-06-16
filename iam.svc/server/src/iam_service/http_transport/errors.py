"""Map ``AppError`` to FastAPI HTTP exceptions."""

from __future__ import annotations

from fastapi import HTTPException

from iam_service.core.errors import AppError, ErrorCodes
from iam_service.validation.http_auth import HttpErrorBody, HttpErrorResponse


def status_code_for_app_error(err: AppError) -> int:
    if err.code == ErrorCodes.UNAUTHENTICATED:
        return 401
    if err.code == ErrorCodes.VALIDATION:
        return 400
    if err.code == ErrorCodes.NOT_FOUND:
        return 404
    if err.code == ErrorCodes.CONFLICT:
        return 409
    return 500


def http_exception_for_app_error(err: AppError) -> HTTPException:
    payload = HttpErrorResponse(
        error=HttpErrorBody(code=err.code, message=err.message),
    )
    return HTTPException(
        status_code=status_code_for_app_error(err),
        detail=payload.model_dump(),
    )

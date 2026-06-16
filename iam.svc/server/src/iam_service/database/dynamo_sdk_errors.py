"""Normalize aioboto3 / botocore failures into ``AppError`` for gRPC mapping."""

from __future__ import annotations

from typing import Final

from botocore.exceptions import ClientError

from iam_service.core.errors import AppError, ErrorCodes
from iam_service.core.results import Failure

# DynamoDB / STS error codes that indicate bad or expired AWS credentials.
_CREDENTIAL_ERROR_CODES: Final[frozenset[str]] = frozenset(
    {
        "UnrecognizedClientException",
        "InvalidSignatureException",
        "IncompleteSignatureException",
        "ExpiredTokenException",
        "InvalidClientTokenId",
        "SignatureDoesNotMatch",
    }
)


def failure_from_dynamo_sdk(message: str, exc: BaseException) -> Failure[None, AppError]:
    """Map ``ClientError`` / ``OSError`` from DynamoDB helpers to ``Failure``."""
    if isinstance(exc, ClientError):
        err_body = exc.response.get("Error", {}) if isinstance(exc.response, dict) else {}
        code = str(err_body.get("Code", "") or "")
        meta = str(err_body.get("Message", "") or str(exc))
        if code in _CREDENTIAL_ERROR_CODES:
            return Failure(
                AppError(
                    code=ErrorCodes.UNAUTHENTICATED,
                    message=(
                        "AWS credentials were rejected for DynamoDB "
                        "(invalid, expired, or wrong keys). "
                        "Refresh ~/.aws/credentials, run `aws sso login`, or fix session tokens."
                    ),
                    detail=f"{code}: {meta}",
                ),
            )
        detail = f"{code}: {meta}" if code else meta
        return Failure(
            AppError(
                code=ErrorCodes.UPSTREAM,
                message=message,
                detail=detail,
            ),
        )
    if isinstance(exc, OSError):
        return Failure(
            AppError(
                code=ErrorCodes.UPSTREAM,
                message=message,
                detail=str(exc),
            ),
        )
    return Failure(
        AppError(
            code=ErrorCodes.INTERNAL,
            message=message,
            detail=str(exc),
        ),
    )

"""Validate raw inputs before filesystem operations."""

from __future__ import annotations

from pathlib import Path

from pydantic import ValidationError

from file_system.core.error_format import format_validation_detail
from file_system.core.errors import AppError, ErrorCodes
from file_system.core.results import Failure, Success
from file_system.core.types import FsResult
from file_system.domain.enums import TextEncoding
from file_system.domain.models import BytesWriteRequest, PathRequest, TextWriteRequest


def validate_path(path: str | Path) -> FsResult[PathRequest]:
    """Validate a filesystem path at the trust boundary."""
    try:
        return Success(PathRequest(path=Path(path)))
    except ValidationError as exc:
        return Failure(
            AppError(
                code=ErrorCodes.VALIDATION,
                message="Invalid path.",
                detail=format_validation_detail(exc),
            ),
        )


def validate_text_write(
    path: str | Path,
    text: str,
    encoding: TextEncoding,
) -> FsResult[TextWriteRequest]:
    """Validate text write inputs."""
    try:
        return Success(
            TextWriteRequest(path=Path(path), text=text, encoding=encoding),
        )
    except ValidationError as exc:
        return Failure(
            AppError(
                code=ErrorCodes.VALIDATION,
                message="Invalid text write request.",
                detail=format_validation_detail(exc),
            ),
        )


def validate_bytes_write(path: str | Path, data: bytes) -> FsResult[BytesWriteRequest]:
    """Validate binary write inputs."""
    try:
        return Success(BytesWriteRequest(path=Path(path), data=data))
    except ValidationError as exc:
        return Failure(
            AppError(
                code=ErrorCodes.VALIDATION,
                message="Invalid binary write request.",
                detail=format_validation_detail(exc),
            ),
        )

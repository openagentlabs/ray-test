"""Map expected filesystem exceptions to ``AppError``."""

from __future__ import annotations

from pathlib import Path

from file_system.core.errors import AppError, ErrorCodes


def io_error(*, operation: str, path: Path, detail: str) -> AppError:
    return AppError(
        code=ErrorCodes.IO,
        message=f"Could not {operation} '{path}'.",
        detail=detail,
    )


def map_os_error(exc: OSError, *, operation: str, path: Path) -> AppError:
    """Translate known ``OSError`` subclasses; re-raise anything unexpected."""
    if isinstance(exc, FileNotFoundError):
        return AppError(
            code=ErrorCodes.NOT_FOUND,
            message=f"Path not found: '{path}'.",
            detail=str(exc),
        )
    if isinstance(exc, PermissionError):
        return AppError(
            code=ErrorCodes.PERMISSION,
            message=f"Permission denied for '{path}'.",
            detail=str(exc),
        )
    if isinstance(exc, IsADirectoryError):
        return AppError(
            code=ErrorCodes.VALIDATION,
            message=f"Expected a file but found a directory: '{path}'.",
            detail=str(exc),
        )
    if exc.errno in {28, 122}:  # ENOSPC, EDQUOT
        return io_error(operation=operation, path=path, detail=str(exc))
    raise exc

"""Canonical ``Result`` aliases for file-system public APIs."""

from __future__ import annotations

from typing import TypeVar

from returns.result import Result

from file_system.core.errors import AppError

T = TypeVar("T")

FsResult = Result[T, AppError]
"""Typed ``Result`` carrying ``AppError`` on failure."""

TextResult = FsResult[str]
"""Text read/write operations."""

BytesResult = FsResult[bytes]
"""Binary read/write operations."""

UnitResult = FsResult[None]
"""Success-without-payload operations."""

__all__ = (
    "BytesResult",
    "FsResult",
    "TextResult",
    "UnitResult",
)

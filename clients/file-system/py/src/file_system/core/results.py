"""``returns`` re-exports and file-system ``Result`` type aliases."""

from __future__ import annotations

from returns.result import Failure, Result, Success

from file_system.core.types import BytesResult, FsResult, TextResult, UnitResult

__all__ = (
    "BytesResult",
    "Failure",
    "FsResult",
    "Result",
    "Success",
    "TextResult",
    "UnitResult",
)

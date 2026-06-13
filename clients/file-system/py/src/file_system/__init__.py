"""High-performance text and binary file I/O for application code."""

from __future__ import annotations

from file_system.cluster import Cluster
from file_system.core.errors import AppError, ErrorCodes
from file_system.core.results import Failure, Success
from file_system.core.types import BytesResult, FsResult, TextResult, UnitResult
from file_system.domain.enums import TextEncoding
from file_system.io.engine import FileEngine, NativeFileEngine

__all__ = (
    "AppError",
    "BytesResult",
    "Cluster",
    "ErrorCodes",
    "Failure",
    "FileEngine",
    "FsResult",
    "NativeFileEngine",
    "Success",
    "TextEncoding",
    "TextResult",
    "UnitResult",
)

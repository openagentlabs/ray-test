"""High-performance filesystem engine implementations."""

from __future__ import annotations

import mmap
import os
import tempfile
from abc import ABC, abstractmethod
from pathlib import Path

from returns.result import Failure, Success

from file_system.core.error_map import map_os_error
from file_system.core.errors import AppError, ErrorCodes
from file_system.core.types import BytesResult, TextResult, UnitResult
from file_system.domain.enums import TextEncoding

_MMAP_THRESHOLD_BYTES = 16 * 1024 * 1024
_WRITE_CHUNK_BYTES = 1024 * 1024


class FileEngine(ABC):
    """Base engine contract for binary and text file access."""

    @abstractmethod
    def read_bytes(self, path: Path) -> BytesResult:
        """Read the full file as bytes."""

    @abstractmethod
    def write_bytes(self, path: Path, data: bytes) -> UnitResult:
        """Write bytes to a file, replacing existing content."""

    @abstractmethod
    def read_text(self, path: Path, encoding: TextEncoding) -> TextResult:
        """Read and decode a text file."""

    @abstractmethod
    def write_text(self, path: Path, text: str, encoding: TextEncoding) -> UnitResult:
        """Encode and write a text file."""


class NativeFileEngine(FileEngine):
    """Stdlib engine using buffered I/O and memory mapping for large reads."""

    def read_bytes(self, path: Path) -> BytesResult:
        try:
            size = path.stat().st_size
        except OSError as exc:
            return Failure(map_os_error(exc, operation="read", path=path))

        if size == 0:
            return Success(b"")

        if size <= _MMAP_THRESHOLD_BYTES:
            try:
                return Success(path.read_bytes())
            except OSError as exc:
                return Failure(map_os_error(exc, operation="read", path=path))

        try:
            with path.open("rb") as handle:
                with mmap.mmap(handle.fileno(), 0, access=mmap.ACCESS_READ) as mapped:
                    return Success(mapped[:])
        except OSError as exc:
            return Failure(map_os_error(exc, operation="read", path=path))

    def write_bytes(self, path: Path, data: bytes) -> UnitResult:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            return Failure(map_os_error(exc, operation="prepare", path=path))

        tmp_path: str | None = None
        try:
            fd, tmp_path = tempfile.mkstemp(
                dir=path.parent,
                prefix=f".{path.name}.",
                suffix=".tmp",
            )
            try:
                offset = 0
                while offset < len(data):
                    written = os.write(fd, data[offset : offset + _WRITE_CHUNK_BYTES])
                    if written == 0:
                        return Failure(
                            AppError(
                                code=ErrorCodes.IO,
                                message=f"Could not write '{path}'.",
                                detail="Write returned zero bytes.",
                            ),
                        )
                    offset += written
            finally:
                os.close(fd)

            os.replace(tmp_path, path)
            tmp_path = None
            return Success(None)
        except OSError as exc:
            if tmp_path is not None:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
            return Failure(map_os_error(exc, operation="write", path=path))

    def read_text(self, path: Path, encoding: TextEncoding) -> TextResult:
        raw = self.read_bytes(path)
        if isinstance(raw, Failure):
            return raw

        try:
            return Success(raw.unwrap().decode(encoding))
        except UnicodeDecodeError as exc:
            return Failure(
                AppError(
                    code=ErrorCodes.ENCODING,
                    message=f"Could not decode '{path}' as {encoding.value}.",
                    detail=str(exc),
                ),
            )

    def write_text(self, path: Path, text: str, encoding: TextEncoding) -> UnitResult:
        try:
            data = text.encode(encoding)
        except UnicodeEncodeError as exc:
            return Failure(
                AppError(
                    code=ErrorCodes.ENCODING,
                    message=f"Could not encode text for '{path}' as {encoding.value}.",
                    detail=str(exc),
                ),
            )
        return self.write_bytes(path, data)

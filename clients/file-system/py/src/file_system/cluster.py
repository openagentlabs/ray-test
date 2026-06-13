"""Public wrapper for high-performance file access."""

from __future__ import annotations

from pathlib import Path

from returns.result import Failure

from file_system.core.types import BytesResult, TextResult, UnitResult
from file_system.domain.enums import TextEncoding
from file_system.io.engine import FileEngine, NativeFileEngine
from file_system.validation.paths import validate_bytes_write, validate_path, validate_text_write


class Cluster:
    """Application-facing wrapper around a ``FileEngine``."""

    def __init__(self, engine: FileEngine | None = None) -> None:
        self._engine = engine or NativeFileEngine()

    def read_bytes(self, path: str | Path) -> BytesResult:
        """Read a file as raw bytes."""
        validated = validate_path(path)
        if isinstance(validated, Failure):
            return Failure(validated.failure())
        return self._engine.read_bytes(validated.unwrap().path)

    def write_bytes(self, path: str | Path, data: bytes) -> UnitResult:
        """Write raw bytes to a file."""
        validated = validate_bytes_write(path, data)
        if isinstance(validated, Failure):
            return Failure(validated.failure())
        request = validated.unwrap()
        return self._engine.write_bytes(request.path, request.data)

    def read_text(
        self,
        path: str | Path,
        encoding: TextEncoding = TextEncoding.UTF8,
    ) -> TextResult:
        """Read and decode a text file."""
        validated = validate_path(path)
        if isinstance(validated, Failure):
            return Failure(validated.failure())
        return self._engine.read_text(validated.unwrap().path, encoding)

    def write_text(
        self,
        path: str | Path,
        text: str,
        encoding: TextEncoding = TextEncoding.UTF8,
    ) -> UnitResult:
        """Encode and write a text file."""
        validated = validate_text_write(path, text, encoding)
        if isinstance(validated, Failure):
            return Failure(validated.failure())
        request = validated.unwrap()
        return self._engine.write_text(request.path, request.text, request.encoding)

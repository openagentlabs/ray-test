"""Unit tests for ``NativeFileEngine``."""

from __future__ import annotations

from pathlib import Path

from returns.result import Failure, Success

from file_system.core.errors import ErrorCodes
from file_system.domain.enums import TextEncoding
from file_system.io.engine import _MMAP_THRESHOLD_BYTES, NativeFileEngine


def test_read_empty_file_returns_empty_bytes(tmp_path: Path) -> None:
    target = tmp_path / "empty.bin"
    target.write_bytes(b"")
    outcome = NativeFileEngine().read_bytes(target)
    assert isinstance(outcome, Success)
    assert outcome.unwrap() == b""


def test_write_creates_parent_directories(tmp_path: Path) -> None:
    target = tmp_path / "nested" / "dir" / "file.bin"
    outcome = NativeFileEngine().write_bytes(target, b"payload")
    assert isinstance(outcome, Success)
    assert target.read_bytes() == b"payload"


def test_write_replaces_existing_content(tmp_path: Path) -> None:
    target = tmp_path / "file.bin"
    engine = NativeFileEngine()
    assert isinstance(engine.write_bytes(target, b"first"), Success)
    assert isinstance(engine.write_bytes(target, b"second"), Success)
    assert target.read_bytes() == b"second"


def test_read_missing_file_returns_not_found(tmp_path: Path) -> None:
    outcome = NativeFileEngine().read_bytes(tmp_path / "missing.bin")
    assert isinstance(outcome, Failure)
    error = outcome.failure()
    assert error is not None
    assert error.code == ErrorCodes.NOT_FOUND


def test_read_directory_returns_validation(tmp_path: Path) -> None:
    outcome = NativeFileEngine().read_bytes(tmp_path)
    assert isinstance(outcome, Failure)
    error = outcome.failure()
    assert error is not None
    assert error.code == ErrorCodes.VALIDATION


def test_read_text_with_bad_encoding_returns_encoding_error(tmp_path: Path) -> None:
    target = tmp_path / "bytes.bin"
    target.write_bytes(b"\xff\xfe")
    outcome = NativeFileEngine().read_text(target, TextEncoding.ASCII)
    assert isinstance(outcome, Failure)
    error = outcome.failure()
    assert error is not None
    assert error.code == ErrorCodes.ENCODING


def test_large_read_uses_mmap_path(tmp_path: Path) -> None:
    target = tmp_path / "large.bin"
    payload = b"x" * (_MMAP_THRESHOLD_BYTES + 1)
    target.write_bytes(payload)
    outcome = NativeFileEngine().read_bytes(target)
    assert isinstance(outcome, Success)
    assert outcome.unwrap() == payload

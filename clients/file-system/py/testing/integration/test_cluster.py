"""Integration tests for ``Cluster`` with ``NativeFileEngine``."""

from __future__ import annotations

from pathlib import Path

from returns.result import Success
from testing.helpers import assert_failure, assert_success

from file_system import Cluster, ErrorCodes, TextEncoding


def test_text_round_trip(tmp_path: Path) -> None:
    cluster = Cluster()
    target = tmp_path / "hello.txt"

    write_outcome = cluster.write_text(target, "hello world")
    assert isinstance(write_outcome, Success)
    assert target.read_text(encoding="utf-8") == "hello world"

    read_outcome = cluster.read_text(target)
    assert assert_success(read_outcome) == "hello world"


def test_bytes_round_trip(tmp_path: Path, sample_bytes: bytes) -> None:
    cluster = Cluster()
    target = tmp_path / "payload.bin"

    assert isinstance(cluster.write_bytes(target, sample_bytes), Success)
    read_outcome = cluster.read_bytes(target)
    assert assert_success(read_outcome) == sample_bytes


def test_read_missing_file_returns_not_found(tmp_path: Path) -> None:
    cluster = Cluster()
    outcome = cluster.read_bytes(tmp_path / "missing.bin")
    error = assert_failure(outcome, code=ErrorCodes.NOT_FOUND)
    assert "not found" in error.message.lower()


def test_read_directory_returns_validation(tmp_path: Path) -> None:
    cluster = Cluster()
    outcome = cluster.read_bytes(tmp_path)
    assert_failure(outcome, code=ErrorCodes.VALIDATION)


def test_read_text_with_bad_encoding_returns_encoding_error(tmp_path: Path) -> None:
    cluster = Cluster()
    target = tmp_path / "bytes.bin"
    target.write_bytes(b"\xff\xfe")

    outcome = cluster.read_text(target, encoding=TextEncoding.ASCII)
    assert_failure(outcome, code=ErrorCodes.ENCODING)


def test_write_text_supports_non_utf8_encodings(tmp_path: Path) -> None:
    cluster = Cluster()
    target = tmp_path / "latin.txt"
    text = "café"

    assert isinstance(
        cluster.write_text(target, text, encoding=TextEncoding.LATIN1),
        Success,
    )
    read_outcome = cluster.read_text(target, encoding=TextEncoding.LATIN1)
    assert assert_success(read_outcome) == text


def test_overwrite_preserves_atomic_replace_semantics(tmp_path: Path) -> None:
    cluster = Cluster()
    target = tmp_path / "state.txt"

    assert isinstance(cluster.write_text(target, "version-1"), Success)
    assert isinstance(cluster.write_text(target, "version-2"), Success)
    assert assert_success(cluster.read_text(target)) == "version-2"

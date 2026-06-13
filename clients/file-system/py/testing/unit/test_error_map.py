"""Unit tests for ``map_os_error``."""

from __future__ import annotations

from pathlib import Path

import pytest

from file_system.core.error_map import io_error, map_os_error
from file_system.core.errors import ErrorCodes


def test_map_file_not_found() -> None:
    path = Path("/tmp/missing.bin")
    error = map_os_error(FileNotFoundError(2, "No such file"), operation="read", path=path)
    assert error.code == ErrorCodes.NOT_FOUND
    assert "not found" in error.message.lower()


def test_map_permission_error() -> None:
    path = Path("/tmp/locked.bin")
    error = map_os_error(PermissionError(13, "Permission denied"), operation="read", path=path)
    assert error.code == ErrorCodes.PERMISSION


def test_map_is_a_directory() -> None:
    path = Path("/tmp/a-directory")
    error = map_os_error(IsADirectoryError(21, "Is a directory"), operation="read", path=path)
    assert error.code == ErrorCodes.VALIDATION


def test_map_enospc_returns_io_error() -> None:
    path = Path("/tmp/full.bin")
    error = map_os_error(OSError(28, "No space left on device"), operation="write", path=path)
    assert error.code == ErrorCodes.IO


def test_map_unexpected_os_error_is_reraised() -> None:
    path = Path("/tmp/other.bin")
    with pytest.raises(OSError):
        map_os_error(OSError(999, "unexpected"), operation="read", path=path)


def test_io_error_helper() -> None:
    path = Path("/tmp/target.bin")
    error = io_error(operation="write", path=path, detail="disk full")
    assert error.code == ErrorCodes.IO
    assert "write" in error.message

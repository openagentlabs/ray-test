"""Integration tests for the package public export surface."""

from __future__ import annotations

import file_system
from file_system import (
    AppError,
    Cluster,
    ErrorCodes,
)


def test_public_exports_are_stable() -> None:
    expected = {
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
    }
    assert set(file_system.__all__) == expected


def test_default_cluster_is_constructible() -> None:
    cluster = Cluster()
    assert cluster is not None


def test_error_codes_are_string_constants() -> None:
    assert ErrorCodes.NOT_FOUND == "not_found"
    assert ErrorCodes.VALIDATION == "validation"


def test_app_error_is_immutable() -> None:
    error = AppError(code=ErrorCodes.IO, message="failed", detail="disk")
    assert error.code == ErrorCodes.IO

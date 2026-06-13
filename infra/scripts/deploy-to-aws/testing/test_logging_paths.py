"""Tests for build log directory layout."""

from __future__ import annotations

from pathlib import Path

from deploy_to_aws.build.constants import (
    FORMAT_LOG_FILENAME,
    LOGGING_BUILDS_DIR,
    LOGGING_DIR,
    RUFF_LOG_FILENAME,
)
from deploy_to_aws.build.logging_paths import (
    build_log_dir,
    build_log_file,
    ensure_build_log_dir,
    logging_root,
    relative_build_log_path,
    ruff_log_path,
)


def test_logging_root_is_application_logging_folder() -> None:
    root = Path("/app/root")
    assert logging_root(root) == root / LOGGING_DIR


def test_build_log_dir_under_application_logging_builds() -> None:
    root = Path("/app/root")
    build_id = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    expected = root / LOGGING_DIR / LOGGING_BUILDS_DIR / build_id
    assert build_log_dir(root, build_id) == expected


def test_ruff_log_path_uses_build_id_folder_and_filename() -> None:
    root = Path("/app/root")
    build_id = "bbbbbbbb-bbbb-cccc-dddd-eeeeeeeeeeee"
    assert ruff_log_path(root, build_id) == (
        root / LOGGING_DIR / LOGGING_BUILDS_DIR / build_id / RUFF_LOG_FILENAME
    )


def test_build_log_file_supports_custom_filenames() -> None:
    root = Path("/app/root")
    build_id = "cccccccc-bbbb-cccc-dddd-eeeeeeeeeeee"
    assert build_log_file(root, build_id, FORMAT_LOG_FILENAME) == (
        root / LOGGING_DIR / LOGGING_BUILDS_DIR / build_id / FORMAT_LOG_FILENAME
    )


def test_ensure_build_log_dir_creates_only_under_logging(tmp_path: Path) -> None:
    build_id = "dddddddd-bbbb-cccc-dddd-eeeeeeeeeeee"
    directory = ensure_build_log_dir(tmp_path, build_id)
    assert directory.is_dir()
    assert directory == tmp_path / LOGGING_DIR / LOGGING_BUILDS_DIR / build_id
    assert not (tmp_path / "output").exists()
    assert not (tmp_path / "build.log").exists()


def test_relative_build_log_path() -> None:
    root = Path("/app/root")
    build_id = "eeeeeeee-bbbb-cccc-dddd-eeeeeeeeeeee"
    assert relative_build_log_path(root, build_id, RUFF_LOG_FILENAME) == (
        f"{LOGGING_DIR}/{LOGGING_BUILDS_DIR}/{build_id}/{RUFF_LOG_FILENAME}"
    )

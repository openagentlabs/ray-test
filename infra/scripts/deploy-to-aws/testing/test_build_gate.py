"""Tests for ruff build gate logging."""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path

from returns.result import Failure, Success

from deploy_to_aws.build.constants import RUFF_LOG_FILENAME
from deploy_to_aws.build.gate import run_build_gate
from deploy_to_aws.build.logging_paths import build_log_dir
from deploy_to_aws.core.errors import ErrorCodes


def _command_key(command: list[str]) -> str:
    if "format" in command:
        return "format_check" if "--check" in command else "format"
    if "--fix" in command:
        return "check_fix"
    return "check"


def _runner_factory(
    outcomes: dict[str, int],
) -> Callable[[list[str], Path], subprocess.CompletedProcess[str]]:
    def _runner(command: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
        _ = cwd
        key = _command_key(command)
        code = outcomes.get(key, 0)
        stderr = "" if code == 0 else f"simulated ruff failure for {key}"
        return subprocess.CompletedProcess(command, code, "stdout", stderr)

    return _runner


def test_build_gate_writes_ruff_log_on_success(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "x"\n', encoding="utf-8"
    )
    build_id = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    result = run_build_gate(
        root=tmp_path,
        build_id=build_id,
        runner=_runner_factory(
            {"check_fix": 0, "format": 0, "check": 0, "format_check": 0},
        ),
    )
    assert isinstance(result, Success)
    log_path = build_log_dir(tmp_path, build_id) / RUFF_LOG_FILENAME
    assert log_path.is_file()
    text = log_path.read_text(encoding="utf-8")
    assert "ruff check --fix" in text
    assert "ruff check --fix ." in text
    assert "ruff format" in text
    assert "ruff format ." in text
    assert "ruff check ." in text
    assert "ruff format --check" in text
    assert "ruff format --check ." in text
    assert f"build_id: {build_id}" in text


def test_build_gate_fails_and_writes_log(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "x"\n', encoding="utf-8"
    )
    build_id = "bbbbbbbb-bbbb-cccc-dddd-eeeeeeeeeeee"
    outcomes = {"check_fix": 1, "format": 0, "check": 0, "format_check": 0}
    result = run_build_gate(
        root=tmp_path,
        build_id=build_id,
        runner=_runner_factory(outcomes),
    )
    assert isinstance(result, Failure)
    err = result.failure()
    assert err.code == ErrorCodes.BUILD
    log_path = build_log_dir(tmp_path, build_id) / RUFF_LOG_FILENAME
    assert log_path.is_file()
    log_text = log_path.read_text(encoding="utf-8")
    assert "simulated ruff failure for check_fix" in log_text

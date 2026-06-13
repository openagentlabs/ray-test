"""Tests for deploy-to-aws-format command."""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest
from returns.result import Failure, Success

from deploy_to_aws.build.constants import FORMAT_LOG_FILENAME
from deploy_to_aws.build.format_code import format_project
from deploy_to_aws.build.logging_paths import build_log_dir
from deploy_to_aws.core.errors import ErrorCodes


def _write_pyproject(root: Path) -> None:
    (root / "pyproject.toml").write_text('[project]\nname = "x"\n', encoding="utf-8")
    pkg = root / "src" / "deploy_to_aws"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("", encoding="utf-8")


def _runner_factory(
    outcomes: dict[str, int],
) -> Callable[[list[str], Path], subprocess.CompletedProcess[str]]:
    def _runner(command: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
        _ = cwd
        if "--fix" in command:
            key = "check_fix"
        elif "format" in command:
            key = "format"
        else:
            key = "check"
        code = outcomes.get(key, 0)
        stderr = "" if code == 0 else f"simulated failure for {key}"
        return subprocess.CompletedProcess(command, code, "stdout", stderr)

    return _runner


def test_format_project_runs_check_fix_then_format(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _write_pyproject(tmp_path)
    calls: list[list[str]] = []

    def _recording_runner(
        command: list[str],
        cwd: Path,
    ) -> subprocess.CompletedProcess[str]:
        _ = cwd
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, "ok", "")

    monkeypatch.setattr(
        "deploy_to_aws.build.format_code.default_runner",
        _recording_runner,
    )

    result = format_project(root=tmp_path)
    assert isinstance(result, Success)
    report = result.unwrap()
    assert len(report.steps) == 2
    assert calls[0][3:6] == ["check", "--fix", "."]
    assert calls[1][3:5] == ["format", "."]
    log_path = build_log_dir(tmp_path, report.build_id) / FORMAT_LOG_FILENAME
    assert report.log_path == str(log_path.relative_to(tmp_path))
    assert log_path.is_file()


def test_format_project_fails_on_check_fix_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _write_pyproject(tmp_path)
    monkeypatch.setattr(
        "deploy_to_aws.build.format_code.default_runner",
        _runner_factory({"check_fix": 1, "format": 0}),
    )

    result = format_project(root=tmp_path)
    assert isinstance(result, Failure)
    assert result.failure().code == ErrorCodes.BUILD
    build_dirs = list((tmp_path / "logging" / "builds").iterdir())
    assert len(build_dirs) == 1
    log_path = build_dirs[0] / FORMAT_LOG_FILENAME
    assert log_path.is_file()

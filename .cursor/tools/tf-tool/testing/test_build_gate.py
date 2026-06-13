"""Unit tests for the ruff build gate."""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest
from returns.result import Failure, Success

from tf_tool.build.gate import run_build_gate
from tf_tool.core.errors import ErrorCodes


def _runner_factory(
    outcomes: dict[str, int],
) -> Callable[[list[str], Path], subprocess.CompletedProcess[str]]:
    def _runner(command: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
        _ = cwd
        key = "check" if "check" in command and "format" not in command else "format"
        code = outcomes.get(key, 0)
        stderr = "" if code == 0 else f"simulated ruff failure for {key}"
        return subprocess.CompletedProcess(command, code, "", stderr)

    return _runner


def test_build_gate_passes_when_ruff_succeeds(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
    result = run_build_gate(root=tmp_path, runner=_runner_factory({"check": 0, "format": 0}))
    assert isinstance(result, Success)
    assert len(result.unwrap().steps) == 2


def test_build_gate_fails_fast_on_ruff_check(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
    result = run_build_gate(root=tmp_path, runner=_runner_factory({"check": 1, "format": 0}))
    assert isinstance(result, Failure)
    err = result.failure()
    assert err.code == ErrorCodes.BUILD
    assert "ruff check" in (err.detail or "")


def test_build_gate_skips_when_installed_without_project_root(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("tf_tool.build.gate.find_project_root", lambda **_kwargs: None)
    result = run_build_gate(root=None, runner=_runner_factory({"check": 0, "format": 0}))
    assert isinstance(result, Success)
    report = result.unwrap()
    assert report.steps[0].name == "skipped-installed"


def test_build_gate_fails_on_format_check(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
    result = run_build_gate(root=tmp_path, runner=_runner_factory({"check": 0, "format": 1}))
    assert isinstance(result, Failure)
    assert "format" in (result.failure().detail or "").lower()

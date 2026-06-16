"""Tests for runtime environment validation."""

from __future__ import annotations

from pathlib import Path

import pytest
from returns.result import Success

from jp_tool.core.env_check import (
    DependencyCheckResult,
    EnvCheckReport,
    PythonCheckResult,
    run_env_check,
)


def test_env_check_passes_in_dev_venv() -> None:
    result = run_env_check()
    assert isinstance(result, Success)
    report = result.unwrap()
    assert report.ok is True
    assert report.python.ok is True
    assert report.python.current.count(".") >= 2
    assert len(report.dependencies) >= 4
    assert all(dep.ok for dep in report.dependencies)
    assert all(dep.installed for dep in report.dependencies)
    assert all(dep.import_ok for dep in report.dependencies)


def test_env_check_skipped_with_env_var(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JP_TOOL_SKIP_ENV_CHECK", "1")
    result = run_env_check()
    assert isinstance(result, Success)
    assert result.unwrap().source == "JP_TOOL_SKIP_ENV_CHECK=1"


def test_env_check_reads_pyproject_when_present(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest = tmp_path / "pyproject.toml"
    manifest.write_text(
        """
[project]
name = "jp-tool"
requires-python = ">=3.12"
dependencies = ["returns>=0.28"]
""".strip(),
        encoding="utf-8",
    )
    src = tmp_path / "src" / "jp_tool"
    src.mkdir(parents=True)
    monkeypatch.setattr("jp_tool.core.env_check.find_project_root", lambda: tmp_path)
    result = run_env_check()
    assert isinstance(result, Success)
    report = result.unwrap()
    assert "pyproject.toml" in report.source
    assert report.dependencies[0].name == "returns"


def test_report_failure_messages() -> None:
    report = EnvCheckReport(
        python=PythonCheckResult(required=">=99.0", current="3.12.0", ok=False),
        dependencies=[
            DependencyCheckResult(
                name="missing-pkg",
                required="missing-pkg>=1.0",
                installed=None,
                import_ok=False,
                ok=False,
            ),
        ],
        source="test",
        ok=False,
    )
    messages = report.failure_messages()
    assert any("Python" in line for line in messages)
    assert any("Missing dependency" in line for line in messages)

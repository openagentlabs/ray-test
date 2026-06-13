"""Tests for pyproject [project] metadata and BuildInfo injection."""

from __future__ import annotations

from pathlib import Path

import pytest
from returns.result import Success

from deploy_to_aws.build.constants import INJECTED_MODULE
from deploy_to_aws.build.inject import inject_build_metadata
from deploy_to_aws.build.prepare import prepare_runtime
from deploy_to_aws.build.project_metadata import ProjectMetadata, load_project_metadata
from deploy_to_aws.build_info import BuildInfo


def _write_pyproject(root: Path, *, version: str = "0.1.0") -> None:
    (root / "pyproject.toml").write_text(
        '[project]\nname = "deploy-to-aws"\n'
        f'version = "{version}"\n'
        'description = "Test app"\n'
        'requires-python = ">=3.12"\n',
        encoding="utf-8",
    )
    (root / "src" / "deploy_to_aws").mkdir(parents=True, exist_ok=True)
    (root / "src" / "deploy_to_aws" / "__init__.py").write_text("", encoding="utf-8")


def test_load_project_metadata_from_pyproject(tmp_path: Path) -> None:
    _write_pyproject(tmp_path)
    loaded = load_project_metadata(tmp_path)
    assert isinstance(loaded, Success)
    project = loaded.unwrap()
    assert project.name == "deploy-to-aws"
    assert project.version == "0.1.0"
    assert project.requires_python == ">=3.12"


def test_inject_build_metadata_writes_static_class(tmp_path: Path) -> None:
    _write_pyproject(tmp_path)
    project = ProjectMetadata(
        name="deploy-to-aws",
        version="1.2.3",
        description="desc",
        requires_python=">=3.12",
    )
    result = inject_build_metadata(
        tmp_path,
        project,
        build_id="11111111-1111-1111-1111-111111111111",
        build_date="2026-06-12T12:00:00+00:00",
    )
    assert isinstance(result, Success)
    module_path = tmp_path / "src" / "deploy_to_aws" / INJECTED_MODULE
    text = module_path.read_text(encoding="utf-8")
    assert "class BuildInfo:" in text
    assert 'build_id: str = "11111111-1111-1111-1111-111111111111"' in text
    assert 'requires_python: str = ">=3.12"' in text
    assert "def app() -> str:" in text


def test_prepare_runtime_injects_from_pyproject(tmp_path: Path) -> None:
    _write_pyproject(tmp_path, version="9.9.9")
    prepared = prepare_runtime(
        root=tmp_path, refresh_build_id=True, run_ruff_gate=False
    )
    assert isinstance(prepared, Success)
    assert prepared.unwrap().version == "9.9.9"


def test_prepare_runtime_ruff_log_matches_injected_build_id(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ruff logs must live at logging/builds/<build_id>/ruff.log."""
    from deploy_to_aws.build.constants import RUFF_LOG_FILENAME
    from deploy_to_aws.build.gate import GateReport, Runner
    from deploy_to_aws.build.logging_paths import build_log_dir, ruff_log_path
    from deploy_to_aws.core.types import DeployResult

    _write_pyproject(tmp_path)

    def _fake_gate(
        *,
        root: Path,
        build_id: str,
        runner: Runner | None = None,
    ) -> DeployResult[GateReport]:
        _ = runner
        log = ruff_log_path(root, build_id)
        log.parent.mkdir(parents=True, exist_ok=True)
        log.write_text(f"build_id: {build_id}\n", encoding="utf-8")
        return Success(
            GateReport(
                build_id=build_id,
                log_path=str(log.relative_to(root)),
                steps=(),
            ),
        )

    monkeypatch.setattr("deploy_to_aws.build.prepare.run_build_gate", _fake_gate)

    prepared = prepare_runtime(root=tmp_path, refresh_build_id=True, run_ruff_gate=True)
    assert isinstance(prepared, Success)
    report = prepared.unwrap()
    expected_log = build_log_dir(tmp_path, report.build_id) / RUFF_LOG_FILENAME
    assert report.ruff_log_path == str(expected_log.relative_to(tmp_path))
    assert expected_log.is_file()
    assert f"build_id: {report.build_id}" in expected_log.read_text(encoding="utf-8")


def test_project_env_override(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _write_pyproject(tmp_path)
    monkeypatch.setenv("DEPLOY_TO_AWS_PROJECT_VERSION", "2.0.0")
    loaded = load_project_metadata(tmp_path)
    assert isinstance(loaded, Success)
    assert loaded.unwrap().version == "2.0.0"


def test_build_info_app_string_contains_fields() -> None:
    text = BuildInfo.app()
    assert "Application:" in text
    assert "Version:" in text
    assert "Description:" in text
    assert "BuildId:" in text

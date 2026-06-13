"""Tests for build package (mocked uv)."""

from __future__ import annotations

import os
import stat
import subprocess
import zipfile
from pathlib import Path

import pytest
from returns.result import Failure, Success

from deploy_to_aws.build.constants import (
    CLI_SCRIPT_NAMES,
    OUTPUT_DIR,
    OUTPUT_DIST_DIR,
    SKIP_BUILD_GATE_ENV,
)
from deploy_to_aws.build.package import build_package


def _write_minimal_project(root: Path) -> None:
    (root / "pyproject.toml").write_text(
        '[project]\nname = "deploy-to-aws"\nversion = "0.1.0"\ndescription = "test"\n',
        encoding="utf-8",
    )
    pkg = root / "src" / "deploy_to_aws"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("", encoding="utf-8")


def _write_console_script(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("#!/usr/bin/env python3\nprint('ok')\n", encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


def _fake_subprocess_run(
    command: list[str],
    cwd: Path,
    **kwargs: object,
) -> subprocess.CompletedProcess[str]:
    if command[:2] == ["uv", "build"]:
        dist_dir = cwd / OUTPUT_DIR / OUTPUT_DIST_DIR
        dist_dir.mkdir(parents=True, exist_ok=True)
        wheel_path = dist_dir / "deploy_to_aws-0.1.0-py3-none-any.whl"
        with zipfile.ZipFile(wheel_path, "w") as archive:
            archive.writestr("deploy_to_aws/__init__.py", "__version__ = '0.1.0'\n")
        return subprocess.CompletedProcess(command, 0, "", "")

    if command[:2] == ["uv", "venv"]:
        venv_dir = Path(command[2])
        for script_name in CLI_SCRIPT_NAMES:
            _write_console_script(venv_dir / "bin" / script_name)
        return subprocess.CompletedProcess(command, 0, "", "")

    if command[:3] == ["uv", "pip", "install"]:
        return subprocess.CompletedProcess(command, 0, "", "")

    return subprocess.CompletedProcess(command, 1, "", "unexpected command")


def test_build_package_creates_output_layout(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(SKIP_BUILD_GATE_ENV, "1")
    _write_minimal_project(tmp_path)
    import deploy_to_aws.build.package as package_module

    original_run = package_module.subprocess.run
    package_module.subprocess.run = lambda *a, **k: _fake_subprocess_run(
        a[0], Path(k["cwd"])
    )  # type: ignore[method-assign, arg-type]
    try:
        result = build_package(root=tmp_path)
    finally:
        package_module.subprocess.run = original_run  # type: ignore[method-assign]

    assert isinstance(result, Success)
    report = result.unwrap()
    assert Path(report.bin_dir).is_dir()
    for script_name in CLI_SCRIPT_NAMES:
        launcher = Path(report.bin_dir) / script_name
        assert launcher.is_file()
        assert os.access(launcher, os.X_OK)


def test_build_package_fails_without_wheel(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(SKIP_BUILD_GATE_ENV, "1")
    _write_minimal_project(tmp_path)

    def _empty_build(
        command: list[str],
        cwd: Path,
        **kwargs: object,
    ) -> subprocess.CompletedProcess[str]:
        if command[:2] == ["uv", "build"]:
            (Path(cwd) / OUTPUT_DIR / OUTPUT_DIST_DIR).mkdir(
                parents=True, exist_ok=True
            )
            return subprocess.CompletedProcess(command, 0, "", "")
        return subprocess.CompletedProcess(command, 1, "", "unexpected")

    import deploy_to_aws.build.package as package_module

    original_run = package_module.subprocess.run
    package_module.subprocess.run = _empty_build  # type: ignore[assignment]
    try:
        result = build_package(root=tmp_path)
    finally:
        package_module.subprocess.run = original_run  # type: ignore[method-assign]

    assert isinstance(result, Failure)

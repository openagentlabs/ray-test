"""Unit tests for package build into ``output/``."""

from __future__ import annotations

import os
import stat
import subprocess
import zipfile
from pathlib import Path

from returns.result import Failure, Success

from jp_tool.build.constants import (
    CLI_SCRIPT_NAMES,
    OUTPUT_APP_DIR,
    OUTPUT_BIN_DIR,
    OUTPUT_DIR,
    OUTPUT_DIST_DIR,
    OUTPUT_ENV_SCRIPT,
)
from jp_tool.build.package import build_package


def _write_minimal_project(root: Path) -> None:
    (root / "pyproject.toml").write_text(
        "[project]\nname='jp-tool'\nversion='0.1.0'\n",
        encoding="utf-8",
    )


def _write_console_script(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("#!/usr/bin/env python3\nprint('ok')\n", encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


def _fake_subprocess_run(command: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    if command[:2] == ["uv", "build"]:
        dist_dir = cwd / OUTPUT_DIR / OUTPUT_DIST_DIR
        dist_dir.mkdir(parents=True, exist_ok=True)
        wheel_path = dist_dir / "jp_tool-0.1.0-py3-none-any.whl"
        with zipfile.ZipFile(wheel_path, "w") as archive:
            archive.writestr("jp_tool/__init__.py", "__version__ = '0.1.0'\n")
            archive.writestr("jp_tool/cli.py", "def main() -> None: ...\n")
        return subprocess.CompletedProcess(command, 0, "", "")

    if command[:2] == ["uv", "venv"]:
        venv_dir = Path(command[2])
        for script_name in CLI_SCRIPT_NAMES:
            _write_console_script(venv_dir / "bin" / script_name)
        _write_console_script(venv_dir / "bin" / "python")
        return subprocess.CompletedProcess(command, 0, "", "")

    if command[:3] == ["uv", "pip", "install"]:
        return subprocess.CompletedProcess(command, 0, "", "")

    return subprocess.CompletedProcess(command, 1, "", "unexpected command")


def test_build_package_extracts_wheel_and_creates_bin_launchers(tmp_path: Path) -> None:
    _write_minimal_project(tmp_path)
    app_dir = tmp_path / OUTPUT_DIR / OUTPUT_APP_DIR
    bin_dir = tmp_path / OUTPUT_DIR / OUTPUT_BIN_DIR
    env_script = tmp_path / OUTPUT_DIR / OUTPUT_ENV_SCRIPT

    import jp_tool.build.package as package_module

    original_run = package_module.subprocess.run
    package_module.subprocess.run = lambda *a, **k: _fake_subprocess_run(a[0], Path(k["cwd"]))  # type: ignore[method-assign, arg-type]
    try:
        result = build_package(root=tmp_path)
    finally:
        package_module.subprocess.run = original_run  # type: ignore[method-assign]

    assert isinstance(result, Success)
    report = result.unwrap()
    assert report.app_dir == str(app_dir)
    assert report.bin_dir == str(bin_dir)
    assert (app_dir / "jp_tool" / "__init__.py").is_file()
    assert env_script.is_file()
    assert 'export PATH="' in env_script.read_text(encoding="utf-8")

    for script_name in CLI_SCRIPT_NAMES:
        launcher = bin_dir / script_name
        assert launcher.is_file()
        assert os.access(launcher, os.X_OK)
        assert launcher.read_text(encoding="utf-8").startswith("#!/usr/bin/env bash")


def test_build_package_fails_when_wheel_missing(tmp_path: Path) -> None:
    _write_minimal_project(tmp_path)

    def _fake_uv_build_only(command: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
        if command[:2] == ["uv", "build"]:
            (Path(cwd) / OUTPUT_DIR / OUTPUT_DIST_DIR).mkdir(parents=True, exist_ok=True)
            return subprocess.CompletedProcess(command, 0, "", "")
        return subprocess.CompletedProcess(command, 1, "", "unexpected command")

    import jp_tool.build.package as package_module

    original_run = package_module.subprocess.run
    package_module.subprocess.run = lambda *a, **k: _fake_uv_build_only(a[0], Path(k["cwd"]))  # type: ignore[method-assign, arg-type]
    try:
        result = build_package(root=tmp_path)
    finally:
        package_module.subprocess.run = original_run  # type: ignore[method-assign]

    assert isinstance(result, Failure)

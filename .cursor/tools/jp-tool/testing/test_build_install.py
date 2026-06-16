"""Unit tests for installing jp-tool onto PATH."""

from __future__ import annotations

import os
import stat
import subprocess
import zipfile
from pathlib import Path

from returns.result import Failure, Success

from jp_tool.build.constants import (
    CLI_SCRIPT_NAMES,
    OUTPUT_DIR,
    OUTPUT_DIST_DIR,
)
from jp_tool.build.install import install_cli
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


def test_install_cli_links_launchers(tmp_path: Path) -> None:
    _write_minimal_project(tmp_path)
    install_dir = tmp_path / "user-bin"

    import jp_tool.build.package as package_module

    original_run = package_module.subprocess.run
    package_module.subprocess.run = lambda *a, **k: _fake_subprocess_run(a[0], Path(k["cwd"]))  # type: ignore[method-assign, arg-type]
    try:
        built = build_package(root=tmp_path)
    finally:
        package_module.subprocess.run = original_run  # type: ignore[method-assign]

    assert isinstance(built, Success)
    installed = install_cli(root=tmp_path, install_dir=install_dir)
    assert isinstance(installed, Success)
    report = installed.unwrap()
    assert report.install_dir == str(install_dir)

    for script_name in CLI_SCRIPT_NAMES:
        wrapper = install_dir / script_name
        assert wrapper.is_file()
        assert os.access(wrapper, os.X_OK)
        assert wrapper.read_text(encoding="utf-8").startswith("#!/usr/bin/env bash")


def test_install_cli_fails_without_build(tmp_path: Path) -> None:
    _write_minimal_project(tmp_path)
    result = install_cli(root=tmp_path, install_dir=tmp_path / "bin")
    assert isinstance(result, Failure)

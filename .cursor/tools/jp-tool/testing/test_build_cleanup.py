"""Unit tests for project cleanup."""

from __future__ import annotations

from pathlib import Path

from returns.result import Success

from jp_tool.build.cleanup import clean_project


def test_clean_project_removes_artifacts(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "jp_tool-0.1.0.whl").write_text("wheel", encoding="utf-8")
    egg_info = tmp_path / "src" / "jp_tool.egg-info"
    egg_info.mkdir(parents=True)
    (egg_info / "PKG-INFO").write_text("info", encoding="utf-8")
    cache = tmp_path / "src" / "jp_tool" / "__pycache__"
    cache.mkdir(parents=True)
    (cache / "cli.cpython-312.pyc").write_bytes(b"pyc")
    scripts = tmp_path / "build"
    scripts.mkdir()
    (scripts / "run.py").write_text("# gate\n", encoding="utf-8")
    setuptools_lib = scripts / "lib"
    setuptools_lib.mkdir()
    (setuptools_lib / "artifact").write_text("x", encoding="utf-8")

    result = clean_project(root=tmp_path)
    assert isinstance(result, Success)
    report = result.unwrap()
    assert not dist.exists()
    assert not egg_info.exists()
    assert not cache.exists()
    assert not setuptools_lib.exists()
    assert (scripts / "run.py").is_file()
    assert len(report.removed) >= 4

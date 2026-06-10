"""End-to-end CLI tests via ``python -m aspire_tool``."""

from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest


def _run_cli(argv: list[str], *, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "aspire_tool", *argv],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )


@pytest.fixture
def registry_env(tmp_path: Path) -> dict[str, str]:
    db = tmp_path / "cli.sqlite"
    env = os.environ.copy()
    env["ASPIRE_REGISTRY_DB"] = str(db)
    return env


@pytest.fixture
def cli_executable(tmp_path: Path) -> Path:
    if os.name == "nt":
        script = tmp_path / "cli_tool.cmd"
        script.write_text("@echo off\r\n", encoding="utf-8")
    else:
        script = tmp_path / "cli_tool.sh"
        script.write_text("#!/usr/bin/env sh\nexit 0\n", encoding="utf-8")
        script.chmod(script.stat().st_mode | stat.S_IXUSR | stat.S_IRUSR)
    return script


def test_cli_manifest_stdout(registry_env: dict[str, str]) -> None:
    proc = _run_cli([], env=registry_env)
    assert proc.returncode == 0, proc.stderr
    data = json.loads(proc.stdout)
    assert data["name"] == "aspire-registry-tool"


def test_cli_add_list_remove(registry_env: dict[str, str], cli_executable: Path) -> None:
    add = _run_cli(
        [
            "-a",
            "-p",
            str(cli_executable),
            "-n",
            "CLI Service",
            "-d",
            "from tests",
        ],
        env=registry_env,
    )
    assert add.returncode == 0, add.stderr
    created = json.loads(add.stdout)
    service_id = created["id"]

    listed = _run_cli(["-l"], env=registry_env)
    assert listed.returncode == 0, listed.stderr
    payload = json.loads(listed.stdout)
    assert any(s["id"] == service_id for s in payload["services"])

    removed = _run_cli(["-r", "-i", service_id], env=registry_env)
    assert removed.returncode == 0, removed.stderr

    listed_after = _run_cli(["-l"], env=registry_env)
    assert listed_after.returncode == 0, listed_after.stderr
    payload_after = json.loads(listed_after.stdout)
    assert all(s["id"] != service_id for s in payload_after["services"])

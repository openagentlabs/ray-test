"""CLI help behavior tests (standard -h / --help / no-args)."""

from __future__ import annotations

import subprocess
import sys

from tf_tool.cli import help_requested
from tf_tool.core.help_text import APP_HELP


def _run_cli(argv: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "tf_tool", *argv],
        capture_output=True,
        text=True,
        check=False,
    )


def test_help_requested_detects_flags() -> None:
    assert help_requested(["--help"]) is True
    assert help_requested(["-h"]) is True
    assert help_requested(["registry-search", "-h"]) is True
    assert help_requested(["helloworld"]) is False


def test_cli_help_long_flag() -> None:
    proc = _run_cli(["--help"])
    assert proc.returncode == 0, proc.stderr
    assert "Usage:" in proc.stdout
    assert "Commands" in proc.stdout
    assert "--help" in proc.stdout
    assert "registry-search" in proc.stdout
    assert "list-aws" in proc.stdout
    assert "Examples:" in proc.stdout
    assert APP_HELP in proc.stdout


def test_cli_help_short_flag() -> None:
    proc = _run_cli(["-h"])
    assert proc.returncode == 0, proc.stderr
    assert "Usage:" in proc.stdout
    assert APP_HELP in proc.stdout


def test_cli_subcommand_help() -> None:
    proc = _run_cli(["registry-search", "--help"])
    assert proc.returncode == 0, proc.stderr
    assert "Search registry modules" in proc.stdout
    assert "--query" in proc.stdout or "-q" in proc.stdout
    assert "Examples:" in proc.stdout
    assert "tf-tool registry-search" in proc.stdout


def test_cli_list_command_help_includes_examples() -> None:
    proc = _run_cli(["list-aws", "--help"])
    assert proc.returncode == 0, proc.stderr
    assert "Browse AWS modules" in proc.stdout
    assert "Examples:" in proc.stdout
    assert "tf-tool list-aws" in proc.stdout
    assert "--json" in proc.stdout


def test_cli_no_args_shows_help() -> None:
    proc = _run_cli([])
    assert proc.returncode == 2
    assert "Usage:" in proc.stdout
    assert APP_HELP in proc.stdout
    assert "--helloworld" in proc.stdout

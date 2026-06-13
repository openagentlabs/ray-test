"""End-to-end CLI action tests via ``python -m tf_tool``."""

from __future__ import annotations

import subprocess
import sys


def _run_cli(argv: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "tf_tool", *argv],
        capture_output=True,
        text=True,
        check=False,
    )


def test_cli_helloworld_flag_default() -> None:
    proc = _run_cli(["--helloworld"])
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip() == "Hello, World!"


def test_cli_helloworld_short_flag_custom_name() -> None:
    proc = _run_cli(["-w", "--name", "Terraform"])
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip() == "Hello, Terraform!"


def test_cli_helloworld_subcommand_default() -> None:
    proc = _run_cli(["helloworld"])
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip() == "Hello, World!"


def test_cli_helloworld_subcommand_custom_name() -> None:
    proc = _run_cli(["helloworld", "--name", "Terraform"])
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip() == "Hello, Terraform!"

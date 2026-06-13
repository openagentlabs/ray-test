"""End-to-end AWS registry search tests via the CLI."""

from __future__ import annotations

import json
import subprocess
import sys


def _run_cli(argv: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "tf_tool", *argv],
        capture_output=True,
        text=True,
        check=False,
    )


def test_cli_registry_search_aws_vpc() -> None:
    proc = _run_cli(
        [
            "registry-search-aws",
            "-q",
            "vpc",
            "--namespace",
            "terraform-aws-modules",
            "--limit",
            "1",
        ],
    )
    assert proc.returncode == 0, proc.stderr
    data = json.loads(proc.stdout)
    assert data["provider"] == "aws"
    assert data["namespace"] == "terraform-aws-modules"
    assert data["count"] == 1
    module = data["modules"][0]
    assert module["provider"] == "aws"
    assert module["name"] == "vpc"
    assert module["namespace"] == "terraform-aws-modules"


def test_cli_search_aws_alias() -> None:
    proc = _run_cli(["search-aws", "-q", "vpc", "--limit", "2"])
    assert proc.returncode == 0, proc.stderr
    data = json.loads(proc.stdout)
    assert data["provider"] == "aws"
    assert all(module["provider"] == "aws" for module in data["modules"])


def test_cli_registry_search_aws_keyword() -> None:
    proc = _run_cli(["registry-search-aws", "-q", "vpc", "--limit", "3"])
    assert proc.returncode == 0, proc.stderr
    data = json.loads(proc.stdout)
    assert data["provider"] == "aws"
    assert data["count"] >= 1
    assert all(module["provider"] == "aws" for module in data["modules"])

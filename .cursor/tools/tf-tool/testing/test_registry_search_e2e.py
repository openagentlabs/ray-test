"""End-to-end registry search tests via the CLI."""

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


def test_cli_registry_search_keyword() -> None:
    proc = _run_cli(["registry-search", "-q", "vpc", "--limit", "2"])
    assert proc.returncode == 0, proc.stderr
    data = json.loads(proc.stdout)
    assert data["query"] == "vpc"
    assert data["count"] >= 1
    assert data["modules"][0]["namespace"]


def test_cli_registry_search_provider_filter() -> None:
    proc = _run_cli(
        [
            "registry-search",
            "-q",
            "vpc",
            "--provider",
            "aws",
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
    assert module["namespace"] == "terraform-aws-modules"
    assert module["provider"] == "aws"
    assert module["name"] == "vpc"


def test_cli_registry_search_rejects_blank_query() -> None:
    proc = _run_cli(["registry-search", "-q", "   "])
    assert proc.returncode == 2
    assert "validation" in proc.stderr.lower() or "Invalid registry search" in proc.stderr

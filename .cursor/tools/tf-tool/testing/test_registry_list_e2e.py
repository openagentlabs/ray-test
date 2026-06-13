"""End-to-end registry list tests via the CLI."""

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


def test_cli_list_aws_modules_table() -> None:
    proc = _run_cli(["list-aws", "--limit", "3"])
    assert proc.returncode == 0, proc.stderr
    assert "Terraform Registry modules" in proc.stdout
    assert "1." in proc.stdout
    assert "2." in proc.stdout
    assert "3." in proc.stdout
    assert "Name" in proc.stdout
    assert "Version" in proc.stdout
    assert "Description" in proc.stdout


def test_cli_list_aws_modules_json() -> None:
    proc = _run_cli(["list-aws", "--limit", "3", "--json"])
    assert proc.returncode == 0, proc.stderr
    data = json.loads(proc.stdout)
    assert data["mode"] == "list"
    assert data["provider"] == "aws"
    assert data["count"] == 3
    assert all(module["provider"] == "aws" for module in data["modules"])
    assert data["modules"][0]["source"].startswith("https://")


def test_cli_list_cloud_provider_json() -> None:
    proc = _run_cli(["list-cloud", "-p", "aws", "--verified", "--limit", "2", "--json"])
    assert proc.returncode == 0, proc.stderr
    data = json.loads(proc.stdout)
    assert data["provider"] == "aws"
    assert data["verified"] is True
    assert data["count"] >= 1


def test_cli_registry_list_with_namespace_json() -> None:
    proc = _run_cli(
        [
            "registry-list",
            "-p",
            "aws",
            "--namespace",
            "terraform-aws-modules",
            "--limit",
            "5",
            "--json",
        ],
    )
    assert proc.returncode == 0, proc.stderr
    data = json.loads(proc.stdout)
    assert data["namespace"] == "terraform-aws-modules"
    assert all(m["namespace"] == "terraform-aws-modules" for m in data["modules"])

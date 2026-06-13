"""End-to-end cloud provider search tests via the CLI."""

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


def test_cli_search_cloud_azure_alias() -> None:
    proc = _run_cli(["search-cloud", "-q", "network", "-p", "azure", "--limit", "2"])
    assert proc.returncode == 0, proc.stderr
    data = json.loads(proc.stdout)
    assert data["provider"] == "azurerm"
    assert all(module["provider"] == "azurerm" for module in data["modules"])


def test_cli_search_cloud_gcp_alias() -> None:
    proc = _run_cli(["search-cloud", "-q", "vpc", "-p", "gcp", "--limit", "2"])
    assert proc.returncode == 0, proc.stderr
    data = json.loads(proc.stdout)
    assert data["provider"] == "google"
    assert all(module["provider"] == "google" for module in data["modules"])


def test_cli_registry_search_accepts_provider_alias() -> None:
    proc = _run_cli(["registry-search", "-q", "vpc", "-p", "amazon", "--limit", "2"])
    assert proc.returncode == 0, proc.stderr
    data = json.loads(proc.stdout)
    assert data["provider"] == "aws"

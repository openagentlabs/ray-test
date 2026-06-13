"""CLI smoke tests."""

from __future__ import annotations

from typer.testing import CliRunner

from pod_manager_cli.main import app

runner = CliRunner()


def test_cli_help() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "pool" in result.stdout

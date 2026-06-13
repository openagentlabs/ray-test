"""Tests for the Cursor AI agent guide card."""

from __future__ import annotations

import subprocess
import sys

from tf_tool.core.agent_help import agent_guide_requested, render_agent_guide


def _run_cli(argv: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "tf_tool", *argv],
        capture_output=True,
        text=True,
        check=False,
    )


def test_agent_guide_requested_detects_flag_and_commands() -> None:
    assert agent_guide_requested(["--agent-help"]) is True
    assert agent_guide_requested(["agent-guide"]) is True
    assert agent_guide_requested(["agent-help"]) is True
    assert agent_guide_requested(["list-aws", "--limit", "1"]) is False
    assert agent_guide_requested(["--help"]) is False


def test_render_agent_guide_includes_required_sections() -> None:
    guide = render_agent_guide()
    assert "TF-TOOL — CURSOR AI AGENT GUIDE" in guide
    assert "WHAT THIS TOOL IS" in guide
    assert "WHEN TO USE" in guide
    assert "SUPPORTED USE CASES" in guide
    assert "EXECUTION EXAMPLES WITH EXPECTED OUTPUT" in guide
    assert "HOW TO GET THIS GUIDE" in guide
    assert "tf-tool --agent-help" in guide
    assert "tf-tool agent-guide" in guide
    assert '"mode": "list"' in guide
    assert '"query": "vpc"' in guide


def test_cli_agent_help_flag() -> None:
    proc = _run_cli(["--agent-help"])
    assert proc.returncode == 0, proc.stderr
    assert "CURSOR AI AGENT GUIDE" in proc.stdout
    assert "WHEN TO USE" in proc.stdout
    assert proc.stderr == ""


def test_cli_agent_guide_command() -> None:
    proc = _run_cli(["agent-guide"])
    assert proc.returncode == 0, proc.stderr
    assert "CURSOR AI AGENT GUIDE" in proc.stdout


def test_cli_agent_help_alias_command() -> None:
    proc = _run_cli(["agent-help"])
    assert proc.returncode == 0, proc.stderr
    assert "HOW TO GET THIS GUIDE" in proc.stdout


def test_cli_root_help_mentions_agent_guide() -> None:
    proc = _run_cli(["--help"])
    assert proc.returncode == 0, proc.stderr
    assert "--agent-help" in proc.stdout
    assert "agent-guide" in proc.stdout


def test_cli_agent_help_rejects_subcommand_combo() -> None:
    proc = _run_cli(["--agent-help", "list-aws"])
    assert proc.returncode == 2
    assert "cannot be combined" in proc.stderr

"""Concise CLI help text and examples for jp-tool."""

from __future__ import annotations

APP_HELP = "Deploy ARB workloads to AWS (Terraform, ECR, Helm)."

OPT_AGENT_HELP = "Print the Cursor AI agent guide card and exit."
AGENT_GUIDE_COMMAND_HELP = "Print the Cursor AI agent guide card (same as --agent-help)."


def format_examples(*lines: str) -> str:
    """Build a Typer/Click epilog with example commands."""
    return "Examples:\n\n" + "\n\n".join(f"  {line}" for line in lines)


APP_EPILOG = (
    format_examples(
        "jp-tool deploy --yes",
        "jp-tool post-deploy --yes --skip-build",
        "jp-tool doctor",
    )
    + "\n\n"
    + "Cursor AI agents: jp-tool --agent-help  (or: jp-tool agent-guide)"
)


def deploy_examples(command: str = "deploy") -> str:
    """Example block for deploy commands."""
    return format_examples(
        f"jp-tool {command} --yes",
        f"jp-tool {command} --skip-preflight --image-tag v1.2.3",
    )

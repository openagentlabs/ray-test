"""Concise CLI help text and examples for tf-tool."""

from __future__ import annotations

APP_HELP = "Browse and search modules on the public Terraform Registry."

OPT_AGENT_HELP = "Print the Cursor AI agent guide card and exit."
AGENT_GUIDE_COMMAND_HELP = "Print the Cursor AI agent guide card (same as --agent-help)."

OPT_QUERY = "Search keyword."
OPT_PROVIDER = "Cloud provider (aws, azure, gcp; aliases: azurerm, google)."
OPT_PROVIDER_REQUIRED = OPT_PROVIDER
OPT_NAMESPACE = "Publisher namespace (e.g. terraform-aws-modules)."
OPT_VERIFIED = "Only verified partner modules."
OPT_LIMIT = "Max results (1-100)."
OPT_OFFSET = "Skip this many results."
OPT_JSON = "Output JSON instead of a numbered table."
OPT_HELLO_NAME = "Name to greet."

LIST_FOOTER = (
    "Shows a numbered table. Enter a row number to download; Esc to exit. "
    "Use --json for raw output."
)


def format_examples(*lines: str) -> str:
    """Build a Typer/Click epilog with example commands."""
    return "Examples:\n\n" + "\n\n".join(f"  {line}" for line in lines)


APP_EPILOG = (
    format_examples(
        "tf-tool list-aws --limit 10",
        "tf-tool search-aws -q vpc --limit 5",
        "tf-tool registry-search -q s3 -p aws --limit 5",
    )
    + "\n\n"
    + "List commands show a numbered table. Enter a row number to download; "
    + "Esc to exit. Use --json for machine-readable output.\n\n"
    + "Cursor AI agents: tf-tool --agent-help  (or: tf-tool agent-guide)"
)


def search_examples(command: str, *, query: str = "vpc") -> str:
    """Example block for registry search commands."""
    return format_examples(
        f"tf-tool {command} -q {query} --limit 5",
        f"tf-tool {command} -q {query} --namespace terraform-aws-modules",
    )


def list_examples(command: str) -> str:
    """Example block for registry list commands."""
    return format_examples(
        f"tf-tool {command} --limit 10",
        f"tf-tool {command} --namespace terraform-aws-modules --limit 5",
        f"tf-tool {command} --limit 5 --json",
    )


def cloud_list_examples(provider: str = "aws") -> str:
    """Example block for list-cloud."""
    return format_examples(
        f"tf-tool list-cloud -p {provider} --limit 10",
        f"tf-tool list-cloud -p {provider} --namespace terraform-aws-modules --limit 5",
        "tf-tool list-cloud -p gcp --limit 5 --json",
    )


def primary_command(name: str, aliases: tuple[str, ...]) -> str:
    """Prefer the short alias in help examples."""
    return aliases[0] if aliases else name

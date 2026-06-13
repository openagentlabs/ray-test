"""Machine- and agent-oriented guide card for tf-tool."""

from __future__ import annotations

import sys

AGENT_HELP_FLAG = "--agent-help"
AGENT_GUIDE_COMMANDS = frozenset({"agent-guide", "agent-help"})


def agent_guide_requested(argv: list[str] | None = None) -> bool:
    """Return True when the user asked for the AI agent guide card."""
    args = sys.argv[1:] if argv is None else argv
    if AGENT_HELP_FLAG in args:
        return True
    return bool(args) and args[0] in AGENT_GUIDE_COMMANDS


def render_agent_guide() -> str:
    """Return the full agent guide card (plain text, sectioned, unambiguous)."""
    return """\
================================================================================
TF-TOOL — CURSOR AI AGENT GUIDE
================================================================================

TOOL_ID:          tf-tool
TOOL_PATH:        .cursor/tools/tf-tool
RUN_AFTER_INSTALL: tf-tool <command> [flags]
AUTH_REQUIRED:    no (public Terraform Registry API only)
BUILD_GATE:       skipped for --agent-help, agent-guide, agent-help, --help, -h

================================================================================
1. WHAT THIS TOOL IS
================================================================================

tf-tool is a terminal CLI that searches and lists Terraform modules on the
public registry at https://registry.terraform.io/.

It does NOT run terraform plan/apply/validate. It does NOT modify your IaC
unless you explicitly download a module via an interactive list prompt.

Two output modes:
  - SEARCH commands → JSON on stdout (module metadata from registry API)
  - LIST commands   → numbered table on stdout; optional download prompt in TTY
                      add --json on list commands for JSON (no prompt)

================================================================================
2. WHEN TO USE (decision rules)
================================================================================

USE tf-tool WHEN:
  - You need to find a Terraform module by keyword (vpc, s3, dynamodb, …)
  - You need to browse modules for a cloud provider without a keyword
  - You need module name, version, description, source URL, or download
  - You need JSON module metadata for scripting or further parsing

DO NOT USE tf-tool WHEN:
  - You need to run terraform init/plan/apply/validate → use terraform CLI
  - You need private registry modules → this tool only queries the PUBLIC registry
  - You need to edit .tf files in the repo → use normal file tools
  - You need non-interactive download in CI → use --json for metadata only;
    download requires TTY row selection on list commands

================================================================================
3. SUPPORTED USE CASES
================================================================================

| ID | Use case                         | Command pattern                    |
|----|----------------------------------|------------------------------------|
| U1 | Search AWS modules by keyword    | tf-tool search-aws -q <kw>        |
| U2 | Search any cloud by keyword      | tf-tool search-cloud -q <kw> -p <> |
| U3 | Generic search + provider      | tf-tool registry-search -q <kw> -p <> |
| U4 | Browse AWS modules (no keyword)  | tf-tool list-aws --limit <n>       |
| U5 | Browse one cloud (no keyword)    | tf-tool list-cloud -p <cloud>      |
| U6 | Browse one publisher namespace   | tf-tool list-aws --namespace <ns>  |
| U7 | Agent/automation (JSON, no prompt)| tf-tool list-aws --limit <n> --json |
| U8 | Smoke test CLI                   | tf-tool helloworld                 |

Provider aliases (resolved automatically):
  azure, microsoft → azurerm
  gcp, google-cloud → google
  amazon, aws → aws

================================================================================
4. COMMANDS (complete list)
================================================================================

SEARCH (stdout = JSON):
  registry-search          Keyword search; optional -p provider
  search-cloud             Keyword search; -p provider REQUIRED
  search-aws               AWS keyword search (alias: registry-search-aws)
  registry-search-google   Google Cloud keyword search
  registry-search-azurerm  Azure keyword search

LIST (stdout = table by default; --json for JSON):
  registry-list            Browse modules; optional -p, --namespace
  list-cloud               Browse modules; -p provider REQUIRED
  list-aws                 AWS browse (alias: registry-list-aws)

META:
  agent-guide              Print this guide card (alias: agent-help)
  helloworld               Smoke test (/ -w / --helloworld on root)

FLAGS (list commands):
  --json                   JSON output; skips table and download prompt
  --limit <1-100>          Max modules returned (default 20)
  --namespace <name>       Filter to publisher (e.g. terraform-aws-modules)
  --verified               Only verified partner modules
  -p, --provider           Cloud provider filter or search-cloud requirement

================================================================================
5. EXECUTION EXAMPLES WITH EXPECTED OUTPUT
================================================================================

--- Example A: Search AWS VPC modules (JSON) ---

COMMAND:
  tf-tool search-aws -q vpc --limit 1

EXIT_CODE: 0
GATE: ruff check runs first (skipped if TF_TOOL_SKIP_BUILD_GATE=1)
STDOUT (JSON; structure is always this shape):
{
  "query": "vpc",
  "provider": "aws",
  "namespace": null,
  "verified": null,
  "limit": 1,
  "offset": 0,
  "meta": { "limit": 1, "current_offset": 0, "next_offset": 1, ... },
  "modules": [
    {
      "id": "terraform-aws-modules/vpc/aws/6.6.1",
      "namespace": "terraform-aws-modules",
      "name": "vpc",
      "version": "6.6.1",
      "provider": "aws",
      "description": "Terraform module to create AWS VPC resources ...",
      "source": "https://github.com/terraform-aws-modules/terraform-aws-vpc",
      "downloads": 190951249,
      "verified": false
    }
  ],
  "count": 1
}
STDERR: empty on success

--- Example B: List AWS modules for agent parsing (JSON, no prompt) ---

COMMAND:
  tf-tool list-aws --limit 2 --json

EXIT_CODE: 0
STDOUT (JSON; structure is always this shape):
{
  "mode": "list",
  "provider": "aws",
  "namespace": null,
  "verified": null,
  "limit": 2,
  "offset": 0,
  "meta": { ... },
  "modules": [ { "id": "...", "namespace": "...", "name": "...", ... } ],
  "count": 2
}
NOTE: --json is REQUIRED for agents in non-TTY contexts (no download prompt).

--- Example C: List AWS modules in TTY (human table + optional download) ---

COMMAND:
  tf-tool list-aws --limit 2

EXIT_CODE: 0
STDOUT (table; row numbers 1..N are download selectors):
Terraform Registry modules (provider=aws) — showing 2:

  #  Name                                       Version      Description
------------------------------------------------------------------------
  1. aws-ia/label/aws                           0.0.6        AWS Label Module
  2. aws-ia/vpc/aws                             4.7.3        AWS VPC Module

Enter row number to download (Esc to exit):
INTERACTIVE: only when stdin is a TTY. Piped/CI stdout ends after the table.

--- Example D: Validation error (structured JSON on stderr) ---

COMMAND:
  tf-tool registry-search -q "   "

EXIT_CODE: 2
STDERR (JSON):
{
  "error": "validation",
  "message": "Invalid registry search request.",
  "detail": "..."
}

================================================================================
6. HOW TO GET THIS GUIDE (for Cursor AI agents)
================================================================================

PRIMARY (recommended for agents):
  tf-tool --agent-help

ALTERNATES (identical content):
  tf-tool agent-guide
  tf-tool agent-help

BEHAVIOR:
  - Prints this card to stdout
  - Exit code 0
  - Skips ruff build gate (same as --help)
  - Do NOT combine --agent-help with another subcommand

HUMAN-ORIENTED HELP (shorter; not agent-focused):
  tf-tool --help
  tf-tool -h
  tf-tool <command> --help

================================================================================
7. ONE-TIME INSTALL
================================================================================

cd .cursor/tools/tf-tool
uv sync --dev
uv run tf-tool-build
uv run tf-tool-install

Then from any directory:
  tf-tool --agent-help

================================================================================
END OF TF-TOOL AGENT GUIDE
================================================================================
"""

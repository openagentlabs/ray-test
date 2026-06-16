"""Machine- and agent-oriented guide card for jp-tool."""

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
JP-TOOL — CURSOR AI AGENT GUIDE
================================================================================

TOOL_ID:          jp-tool
TOOL_PATH:        .cursor/tools/jp-tool
RUN_AFTER_INSTALL: jp-tool <command> [flags]
AUTH_REQUIRED:    yes (AWS CLI profile per app_config.toml / constants.mdc)
BUILD_GATE:       skipped for --agent-help, agent-guide, agent-help, --help, -h

================================================================================
1. WHAT THIS TOOL IS
================================================================================

jp-tool is a terminal CLI that deploys ARB workloads to AWS:
Terraform apply, Docker build, ECR push, Helm rollout, and validation.

It does NOT replace raw terraform/helm/kubectl for ad-hoc debugging.
It orchestrates the full deploy pipeline for this monorepo.

================================================================================
2. WHEN TO USE (decision rules)
================================================================================

USE jp-tool WHEN:
  - You need the full AWS deploy pipeline (Terraform → build → ECR → Helm)
  - You need post-Terraform rollout only (post-deploy)
  - You need a typed, config-driven deploy with preflight checks

DO NOT USE jp-tool WHEN:
  - You only need terraform plan/validate → use terraform CLI from infra/aws/aws_tf/
  - You only need registry module search → use tf-tool
  - You need to edit .tf or Helm charts → use normal file tools first

================================================================================
3. SUPPORTED USE CASES
================================================================================

| ID | Use case                         | Command pattern                    |
|----|----------------------------------|------------------------------------|
| U1 | Full deploy pipeline             | jp-tool deploy --yes               |
| U2 | Post-Terraform rollout only      | jp-tool post-deploy --yes          |
| U3 | Skip Docker build                | jp-tool deploy --yes --skip-build  |
| U4 | Skip preflight checks            | jp-tool deploy --yes --skip-preflight |
| U5 | Override image tag               | jp-tool deploy --yes --image-tag <tag> |
| U6 | Validate Python + deps           | jp-tool doctor                     |
| U7 | Agent guide (this card)          | jp-tool --agent-help               |

================================================================================
4. COMMANDS (complete list)
================================================================================

DEPLOY:
  deploy           Full pipeline: configure → preflight → terraform → build → ECR → Helm
  post-deploy      Skip Terraform; run build/ECR/Helm/validate after prior apply

META:
  doctor           Validate Python and runtime dependencies (alias: env-check)
  agent-guide      Print this guide card (alias: agent-help)

FLAGS (deploy / post-deploy):
  --yes              Auto-approve terraform apply
  --skip-build       Skip Docker image build
  --skip-scaffold    Skip secrets scaffold phase
  --skip-preflight   Skip tool and AWS preflight checks
  --image-tag <tag>  Override container image tag
  --no-cache         Build Docker images without cache

================================================================================
5. EXECUTION EXAMPLES
================================================================================

--- Example A: Full deploy (auto-approve) ---

COMMAND:
  jp-tool deploy --yes

EXIT_CODE: 0 on success
GATE: ruff check runs first (skipped if JP_TOOL_SKIP_BUILD_GATE=1)
STDOUT: Phase summary text on success
STDERR: JSON error on validation failure (exit 2)

--- Example B: Post-deploy only ---

COMMAND:
  jp-tool post-deploy --yes --skip-build

--- Example C: Environment doctor (JSON) ---

COMMAND:
  jp-tool doctor

EXIT_CODE: 0 pass · 2 fail
STDOUT: JSON with python + dependency versions

--- Example D: Validation error (structured JSON on stderr) ---

EXIT_CODE: 2
STDERR (JSON):
{
  "error": "validation",
  "message": "...",
  "detail": "..."
}

================================================================================
6. HOW TO GET THIS GUIDE (for Cursor AI agents)
================================================================================

PRIMARY (recommended for agents):
  jp-tool --agent-help

ALTERNATES (identical content):
  jp-tool agent-guide
  jp-tool agent-help

BEHAVIOR:
  - Prints this card to stdout
  - Exit code 0
  - Skips ruff build gate (same as --help)
  - Do NOT combine --agent-help with another subcommand

================================================================================
7. ONE-TIME INSTALL
================================================================================

cd .cursor/tools/jp-tool
uv sync --dev
uv run jp-tool-build
uv run jp-tool-install

Then from any directory:
  jp-tool --agent-help

================================================================================
8. CONFIGURATION
================================================================================

Runtime config: app_config.toml (PascalCase sections)
Env overrides: JP_TOOL_<SECTION>_<FIELD> (UPPERCASE, wins over TOML)

See README.md for App/Aws/Deploy/Paths sections and AWS profile requirements.
Link project constants: .cursor/rules/constants/constants.mdc (AWS_CLI_PROFILE, etc.)

================================================================================
END OF JP-TOOL AGENT GUIDE
================================================================================
"""

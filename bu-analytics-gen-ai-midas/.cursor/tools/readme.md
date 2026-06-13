# MIDAS Cursor Tools — Registry

> **Schema version:** 1.0  
> **Location:** `.cursor/tools/`  
> **Purpose:** This file is the single source of truth listing every tool available
> to Cursor skills in this project. Each tool has a companion `<name>.TOOL.md`
> descriptor that the skill reads before invoking the tool.

---

## How to use this registry (for skills / agents)

1. **Discover** — Read this file to find the tool that matches the user's intent.
2. **Describe** — Read the tool's `*.TOOL.md` file to learn its inputs, outputs,
   flags, internal functions, and safe invocation patterns.
3. **Confirm** (when destructive or writes files) — show the user a `--dry-run` first.
4. **Execute** — run the tool via `Shell` with the correct flags.
5. **Report** — surface the tool's stdout/stderr back to the user in the TASK REPORT.

---

## How to add a new tool to this registry

1. Place single-file scripts under `.cursor/tools/<tool-name>.<ext>`, **or** create a **uv project subdirectory** (see [`jira_tool/`](jira_tool/)): `pyproject.toml`, package folder, `TOOL.md`, `uv.lock`; install with `uv sync --project .cursor/tools/<dir>`.
2. **Python tools must use:** Python 3.11+, full type hints, and a **Pydantic v2
   `BaseModel`** as the single source of truth for all inputs, defaults, and
   validation — either in the uv package (preferred for new tools) or as in `aws-sso-configure-tool.py` for legacy single-file tools.
3. Create **`TOOL.md`** next to the tool (project root for uv packages, or `.cursor/tools/<name>.TOOL.md` for single-file tools) using the **gold-standard format** (sections 1–10 are required).
4. Add a row to the table below.
5. Reference the tool in the relevant skill's `SKILL.md` under a **Tools** section.

**Gold-standard `TOOL.md` section checklist:**

| # | Section | Required |
|---|---------|----------|
| 1 | Purpose + when to invoke | Yes |
| 2 | Prerequisites | Yes |
| 3 | Invocation examples | Yes |
| 4 | Flags / Inputs table | Yes |
| 5 | Internal functions table | Yes |
| 6 | Outputs (file, stdout, stderr, exit codes) | Yes |
| 7 | Project-specific defaults reference | Yes |
| 8 | Recommended agent workflow | Yes |
| 9 | Related tools / next-step commands | Yes |
| 10 | Security notes | Yes |

---

## Tool inventory

| Tool file | Descriptor | Category | Description | Key flags |
|-----------|------------|----------|-------------|-----------|
| `aws-sso-configure-tool.py` | [`aws-sso-configure.TOOL.md`](aws-sso-configure.TOOL.md) | AWS Auth | Write an AWS SSO profile to `~/.aws/config`; optionally trigger `aws sso login`. Python 3.11 · Pydantic v2 · fully type-annotated. | `--login`, `--dry-run`, `--profile`, `--account-id`, `--role-name` |
| [`fortify_workbook_extract/`](fortify_workbook_extract/) (`parse_isg_code_scan_report_tool.py`) | [`.cursor/skills/fortify_workbook_extract/SKILL.md`](../skills/fortify_workbook_extract/SKILL.md) | Security | Extract Fortify/ISG Developer Workbook PDFs to CSV/JSON/YAML; JSON job API for agents. | `--tool-card-json`, `--pdf`, `--json-config` |
| [`jira_tool/`](jira_tool/) (`jira-tool` CLI via uv) | [`jira_tool/TOOL.md`](jira_tool/TOOL.md) | Project Tracking | Jira REST API operations: create/edit/search tickets, epics, boards, sprints, subtasks, users, labels. API-key auth. All output is JSON. | `--key`, `--project`, `--jql`, `--board`, `--sprint-id`, `--url`, `--email`, `--token` |

---

## Category definitions

| Category | Examples |
|----------|----------|
| **AWS Auth** | SSO setup, credential helpers, profile management |
| **AWS Infra** | Terraform wrappers, IAM validators, resource checks |
| **AWS Connect** | SSM port-forwards, tunnel scripts, kubectl proxies |
| **AWS Validate** | Security group checks, endpoint probes, connectivity tests |
| **Secrets** | Secrets Manager read/write helpers, populate scripts |
| **Build / CI** | Docker build helpers, ECR push, Helm deploy wrappers |
| **Dev Setup** | Local environment, Docker Compose, venv helpers |
| **Project Tracking** | Jira ticket management, sprint ops, board queries |

---

## Naming conventions

| Item | Convention | Example |
|------|------------|---------|
| Tool script | `<verb>-<noun>-tool.<ext>` or existing script name | `aws-sso-configure-tool.py` |
| Tool descriptor | `<stem>.TOOL.md` (avoid `...-tool.TOOL.md`) | `aws-sso-configure.TOOL.md` |
| Internal function names | `snake_case` | `write_profile`, `ensure_aws_cli` |
| Flag names | `--kebab-case` | `--dry-run`, `--sso-region` |

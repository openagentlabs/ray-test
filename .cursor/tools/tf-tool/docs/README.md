# tf-tool Documentation

## TLDR

**tf-tool** browses and searches the public [Terraform Registry](https://registry.terraform.io/) from the terminal — no auth required.

```bash
cd .cursor/tools/tf-tool && uv sync --dev && uv run tf-tool-build && uv run tf-tool-install
tf-tool list-aws --limit 10          # numbered table; pick a row to download
tf-tool search-aws -q vpc --limit 5  # keyword search (JSON)
tf-tool --help                       # all commands + examples
```

| Need | Command |
|------|---------|
| Browse AWS modules | `tf-tool list-aws --limit 10` |
| Search by keyword | `tf-tool search-aws -q vpc --limit 5` |
| Filter by cloud | `tf-tool search-cloud -q network -p azure` |
| Scripting / CI | add `--json` to list commands |
| Help (humans) | `tf-tool --help` or `tf-tool <command> --help` |
| **Agent guide card** | `tf-tool --agent-help` or `tf-tool agent-guide` |

---

## Cursor AI agent guide

**Use this first** when a Cursor agent needs to understand tf-tool with zero ambiguity.

```bash
tf-tool --agent-help
# same output:
tf-tool agent-guide
tf-tool agent-help
```

The card prints to **stdout**, **exit 0**, and **skips** the ruff build gate (like `--help`).

It includes:

| Section | Content |
|---------|---------|
| What this tool is | Registry search/list only; not terraform plan/apply |
| When to use / not use | Explicit decision rules |
| Use cases | U1–U8 with command patterns |
| Commands | Full command list + flags |
| Examples | Commands with **expected stdout shape** (JSON and table) |
| How to get this guide | `--agent-help`, `agent-guide`, `agent-help` |

**Agents in CI/non-TTY:** always add `--json` to list commands (no download prompt).

**Human help** (`tf-tool --help`) is shorter and not agent-focused.

---

## Use cases

| Scenario | What to run |
|----------|-------------|
| **Find a module template** | `tf-tool search-aws -q vpc` or `tf-tool registry-search -q s3 -p aws` |
| **Browse without a keyword** | `tf-tool list-aws --limit 20` or `tf-tool list-cloud -p aws` |
| **Explore one publisher** | `tf-tool list-aws --namespace terraform-aws-modules --limit 10` |
| **Download into cwd** | Run a list command in a TTY, enter row number; module lands in `./{namespace}-{name}/` |
| **Agent / automation** | `tf-tool list-aws --limit 5 --json` — table and download prompt are skipped |
| **Smoke test the CLI** | `tf-tool helloworld` or `tf-tool -w` |

Provider aliases resolve automatically: `azure`→`azurerm`, `gcp`→`google`, `amazon`→`aws`.

---

## Help

| Invocation | Audience | Exit |
|------------|----------|------|
| `tf-tool --agent-help` | **Cursor AI agents** (full guide card) | `0` |
| `tf-tool agent-guide` / `agent-help` | Same agent card | `0` |
| `tf-tool --help` / `-h` | Humans — commands + short examples | `0` |
| `tf-tool <command> --help` | Humans — flags for one command | `0` |
| `tf-tool` (no args) | Same as `--help` | `2` |

Agent and standard help **skip** the ruff quality gate.

```bash
tf-tool --agent-help          # agent card (start here for agents)
tf-tool --help
tf-tool list-aws --help
```

**Root help shows:**

- One-line summary: *Browse and search modules on the public Terraform Registry.*
- Command list with short descriptions
- Examples: `list-aws`, `search-aws`, `registry-search`

**List commands** also document the interactive flow: numbered table → enter row to download → Esc to exit.

---

## Commands

### Registry — search (JSON output)

| Command | When to use |
|---------|-------------|
| `registry-search` | Keyword search; optional `-p` provider |
| `search-cloud` | Keyword search; **requires** `-p` provider |
| `search-aws` / `registry-search-aws` | AWS only; no `-p` needed |
| `registry-search-google` | Google Cloud only |
| `registry-search-azurerm` | Azure only |

```bash
tf-tool search-aws -q vpc --limit 5
tf-tool search-aws -q vpc --namespace terraform-aws-modules
tf-tool search-cloud -q network -p azure --limit 5
tf-tool registry-search -q s3 -p aws --limit 5
```

| Flag | Purpose |
|------|---------|
| `-q`, `--query` | Search keyword (**required**) |
| `-p`, `--provider` | Cloud provider (`search-cloud` / `registry-search` only) |
| `--namespace` | Publisher filter (e.g. `terraform-aws-modules`) |
| `--verified` | Verified partner modules only |
| `--limit` | Max results, 1–100 (default 20) |
| `--offset` | Pagination offset |

API: `GET https://registry.terraform.io/v1/modules/search` — [Registry API docs](https://developer.hashicorp.com/terraform/registry/api-docs#search-modules).

### Registry — list (table + optional download)

| Command | When to use |
|---------|-------------|
| `registry-list` | Browse all modules; optional `-p`, `--namespace` |
| `list-cloud` | Browse one cloud; **requires** `-p` |
| `list-aws` / `registry-list-aws` | AWS only |

```bash
tf-tool list-aws --limit 10
tf-tool list-aws --namespace terraform-aws-modules --limit 5
tf-tool list-cloud -p aws --verified --limit 5
tf-tool registry-list -p aws --limit 10 --json    # no prompt; JSON only
```

| Flag | Purpose |
|------|---------|
| `-p`, `--provider` | Cloud provider filter |
| `--namespace` | Browse one publisher |
| `--verified` | Verified partner modules only |
| `--limit` / `--offset` | Pagination |
| `--json` | JSON output; skips table and download prompt |

**Default output** — numbered rows (`#`, name, version, description):

```text
  1. terraform-aws-modules/vpc/aws    6.6.1    Terraform module to create AWS VPC resources
  2. aws-ia/label/aws                 0.0.6    AWS Label Module

Enter row number to download (Esc to exit):
```

Download resolves the registry `X-Terraform-Get` source (GitHub archive) into `./{namespace}-{name}/` in the current directory.

API: `GET https://registry.terraform.io/v1/modules` or `.../v1/modules/:namespace` — [List modules](https://developer.hashicorp.com/terraform/registry/api-docs#list-modules).

### Tooling (build / dev)

| Command | Purpose |
|---------|---------|
| `uv sync --dev` | Install `.venv` + dev tools |
| `uv run tf-tool-build` | Build wheel into `output/` |
| `uv run tf-tool-install` | Install `tf-tool` to `~/.local/bin` |
| `uv run tf-tool-clean` | Remove `output/` and caches |
| `uv run pytest` | Run tests (68+) |

Set `TF_TOOL_SKIP_BUILD_GATE=1` to skip the automatic ruff check before CLI runs (debug only).

---

## Development

```bash
cd .cursor/tools/tf-tool
uv sync --dev
uv run pytest
uv run ruff check
uv run mypy
```

Every `tf-tool` run (except `--help`) runs `ruff check` and `ruff format --check` first.

---

## More detail

Full build output, project layout, and action authoring: [project README](../README.md).

Stack rules: `.cursor/rules/python/python.mdc`, `.cursor/rules/terrafrom.mdc`.

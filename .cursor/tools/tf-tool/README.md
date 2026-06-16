# tf-tool

UV-managed CLI under **`.cursor/tools/tf-tool`**: Terraform helpers for Cursor AI agents.

Uses **Typer** for commands, **Pydantic** for ingress validation and API response schemas, and **`returns`** `Result` for explicit success and failure paths. Each feature is a self-contained **action** under `src/tf_tool/actions/`.

| Section | Topic |
|---------|-------|
| [Getting started](#getting-started) | Install, build, clean, and run |
| [Help](#help) | Standard `-h` / `--help` behavior |
| [Commands](#commands) | UV and tf-tool command reference |
| [Build output](#build-output) | `output/` folder layout |
| [Actions](#actions) | Available subcommands |
| [Registry search](#registry-search) | Search Terraform modules |
| [Registry list](#registry-list) | Browse modules without a keyword |
| [Quality gate](#quality-gate) | Automatic ruff checks before run |
| [Project layout](#project-layout) | Source tree |
| [Adding a new action](#adding-a-new-action) | Plugin pattern |
| [Development](#development) | Tests and manual quality checks |
| [Documentation](#documentation) | Extended docs |

---

## Getting started

```bash
cd .cursor/tools/tf-tool
uv sync --dev
```

`uv sync --dev` creates `.venv`, installs runtime dependencies, and dev tools (ruff, mypy, pytest).

**Typical workflow:**

```bash
uv run tf-tool-build          # build package into output/
uv run tf-tool-install        # link tf-tool into ~/.local/bin (on PATH)
tf-tool --help                # run from any directory
tf-tool search-aws -q vpc --limit 5
tf-tool list-aws --limit 5
uv run tf-tool-clean          # remove build artifacts when done
```

One-time setup to run `tf-tool` from any terminal:

```bash
cd .cursor/tools/tf-tool
uv sync --dev
uv run tf-tool-build
uv run tf-tool-install
```

`tf-tool-install` symlinks `output/bin/tf-tool` into `~/.local/bin`. Override with `TF_TOOL_INSTALL_DIR=/path/to/bin`.

Re-install after dependency or lockfile changes:

```bash
uv sync --dev
```

---

## Help

Standard CLI help (Typer/Click conventions):

| Invocation | Output | Exit code |
|------------|--------|-----------|
| `uv run tf-tool --help` | Full help on stdout | `0` |
| `uv run tf-tool -h` | Same as `--help` | `0` |
| `uv run tf-tool` | Help when no subcommand | `2` |
| `uv run tf-tool <command> --help` | Subcommand help | `0` |

```bash
uv run tf-tool --help
uv run tf-tool -h
uv run tf-tool registry-search --help
```

Help requests **skip the ruff quality gate** so usage is always available.

**Cursor AI agents** should run `tf-tool --agent-help` (or `tf-tool agent-guide`) first — a structured guide card with use cases, commands, and expected output examples. See [`docs/README.md`](docs/README.md#cursor-ai-agent-guide).

---

## Commands

| Command | What it does |
|---------|----------------|
| `uv sync --dev` | Install dependencies into `.venv` |
| `uv run tf-tool-build` | Build package into `output/` (does not run the app) |
| `uv run tf-tool-clean` | Remove `output/`, caches, and build artifacts |
| `uv run python build/package.py` | Same as `tf-tool-build` |
| `uv run python build/clean.py` | Same as `tf-tool-clean` |
| `uv run python build/run.py` | Run ruff quality gate only |
| `uv run tf-tool ...` | Quality gate, then CLI command |
| `uv build --out-dir output/dist` | Low-level wheel/sdist build only |
| `uv run pytest` | Run test suite |
| `uv run ruff check` | Lint |
| `uv run ruff format --check` | Format check |
| `uv run mypy` | Type check |

> **Note:** `uv clean` clears the **global uv cache**, not this project's build files. Use `uv run tf-tool-clean` for local artifacts.

### Environment variables

| Variable | Purpose |
|----------|---------|
| `TF_TOOL_SKIP_BUILD_GATE=1` | Skip automatic ruff gate before CLI (debugging only) |

---

## Build output

Build with:

```bash
uv run tf-tool-build
```

After build, **`output/`** contains the application artifacts and runnable launchers:

```
output/
  bin/
    tf-tool                   # executable symlinks (chmod +x targets)
    tf-tool-build
    tf-tool-clean
  venv/                       # isolated runtime with wheel installed
  env.sh                      # exports output/bin onto PATH
  dist/
    tf_tool-<version>-py3-none-any.whl
    tf_tool-<version>.tar.gz
  app/
    tf_tool/                  # extracted application package
    tf_tool-<version>.dist-info/
```

Run from any directory after build:

```bash
source .cursor/tools/tf-tool/output/env.sh   # once per shell session
tf-tool --help
tf-tool registry-search -q vpc --provider aws --limit 5
```

Or add `output/bin` permanently (example for bash):

```bash
export PATH="/absolute/path/to/.cursor/tools/tf-tool/output/bin:$PATH"
```

Clean with:

```bash
uv run tf-tool-clean
```

Removes `output/`, legacy `dist/`, `*.egg-info`, setuptools build debris under `build/`, and tool caches (`.pytest_cache`, `.mypy_cache`, `.ruff_cache`). Does **not** remove `.venv`.

---

## Actions

### Run examples

```bash
uv run tf-tool --help
uv run tf-tool helloworld
uv run tf-tool helloworld -n Terraform
uv run tf-tool --helloworld              # flag alias: -w
uv run tf-tool -w -n Terraform
uv run tf-tool search-aws -q vpc --limit 5
tf-tool list-aws --limit 5
uv run tf-tool registry-search-aws -q vpc --namespace terraform-aws-modules --limit 5
uv run tf-tool registry-search-aws -q vpc --namespace terraform-aws-modules --limit 5
uv run tf-tool registry-search-google -q network --limit 5
uv run tf-tool registry-search-azurerm -q network --limit 5
```

Module entry (equivalent):

```bash
uv run python -m tf_tool
uv run python -m tf_tool helloworld
uv run python -m tf_tool registry-search -q dynamodb --limit 3
```

### `helloworld`

Print a hello-world greeting. Available as a subcommand or via `-w` / `--helloworld` on the root command.

### `registry-search`

Search Terraform modules on the public [Terraform Registry](https://registry.terraform.io/). **No authentication required.**

Gold-standard API (used by all registry commands):

`GET https://registry.terraform.io/v1/modules/search?q=<query>&provider=<provider>&namespace=<ns>&verified=<bool>&limit=<n>&offset=<n>`

See [HashiCorp Registry API — Search Modules](https://developer.hashicorp.com/terraform/registry/api-docs#search-modules).

| Flag | Purpose |
|------|---------|
| `-q`, `--query` | Keyword or phrase (required) |
| `-p`, `--provider` | Cloud name or slug (`aws`, `azure`, `gcp`, …); aliases resolved |
| `--namespace` | Filter by publisher namespace |
| `--verified` / `--all` | Restrict to verified partner modules |
| `--limit` | Page size (1–100, default 20) |
| `--offset` | Pagination offset |

### `search-cloud` (provider required)

Search by **cloud provider name**; aliases are resolved automatically (`azure`→`azurerm`, `gcp`→`google`, `amazon`→`aws`):

```bash
uv run tf-tool search-cloud -q network -p azure --limit 5
uv run tf-tool search-cloud -q vpc -p aws --namespace terraform-aws-modules
```

### Provider-scoped search (`registry-search-<cloud>`)

One action per cloud provider under `actions/registry_search/providers/<cloud>/`. Each command locks `provider` so you do not pass `--provider` manually.

| Command | Provider | Example |
|---------|----------|---------|
| `search-aws` / `registry-search-aws` | `aws` | `tf-tool search-aws -q vpc --namespace terraform-aws-modules` |
| `registry-search-google` | `google` | `tf-tool registry-search-google -q lb-http` |
| `registry-search-azurerm` | `azurerm` | `tf-tool registry-search-azurerm -q network` |

Provider actions accept the same flags as `registry-search` except `--provider`.

```bash
uv run tf-tool search-aws -q vpc --limit 5
tf-tool list-aws --limit 5
uv run tf-tool registry-search-aws -q vpc --namespace terraform-aws-modules --limit 5
uv run tf-tool registry-search -q network --verified --limit 10
uv run tf-tool registry-search -q vpc --namespace terraform-aws-modules --limit 1
```

## Registry list

### `registry-list` (browse without keyword)

List modules on the public Terraform Registry when you do not have a search keyword — useful for discovering downloadable templates by provider or namespace.

Gold-standard API:

`GET https://registry.terraform.io/v1/modules` or `GET .../v1/modules/:namespace`

Supports `provider`, `verified`, `limit`, `offset` (no `q`).

| Flag | Purpose |
|------|---------|
| `-p`, `--provider` | Cloud name or slug (`aws`, `azure`, `gcp`, …) |
| `--namespace` | Browse a publisher namespace (e.g. `terraform-aws-modules`) |
| `--verified` / `--all` | Restrict to verified partner modules |
| `--limit` | Page size (1–100, default 20) |
| `--offset` | Pagination offset |

```bash
uv run tf-tool registry-list -p aws --limit 10
uv run tf-tool registry-list -p aws --namespace terraform-aws-modules --limit 5
uv run tf-tool list-cloud -p aws --verified --limit 5
uv run tf-tool list-aws --limit 5
```

By default, list commands print a **numbered table** (`#`, name, version, description). After the table, enter a row number to download that module into the current directory, or press **Esc** to exit. Use `--json` for machine-readable output (no prompt).

```text
Terraform Registry modules (provider=aws) — showing 3:

  #  Name                                     Version      Description
-----------------------------------------------------------------------
  1. terraform-aws-modules/vpc/aws          6.6.1        Terraform module to create AWS VPC resources
  2. aws-ia/label/aws                        0.0.6        AWS Label Module

Enter row number to download (Esc to exit): 1

Downloading terraform-aws-modules/vpc/aws v6.6.1 ...
Downloaded to /your/cwd/terraform-aws-modules-vpc
```

---

## Quality gate

Every `tf-tool` run (except `--help` / `-h`) executes the **ruff quality gate** first:

1. `ruff check src testing`
2. `ruff format --check src testing`

If either fails, the CLI exits before any action runs. This is separate from `uv run tf-tool-build`.

```bash
uv run python build/run.py    # manual gate only
uv run tf-tool ...            # gate, then command
```

Implementation: `src/tf_tool/build/gate.py` and `build/run.py`.

---

## Project layout

```
.cursor/tools/tf-tool/
  build/                    # manual script entrypoints (run, clean, package)
  docs/                     # extended documentation
  output/                   # build artifacts (gitignored)
  src/tf_tool/
    actions/                # one subfolder per action
      action_base.py
      bootstrap.py
      helloworld/
      registry_search/      # shared client, models, generic registry-search
        providers/          # one subfolder per cloud provider
          provider_action_base.py
          aws/              # registry-search-aws, registry-list-aws
          provider_list_action_base.py
          google/           # registry-search-google
          azurerm/          # registry-search-azurerm
    action_manager/
    build/                  # gate, cleanup, package logic
    core/
    cli.py
  testing/                  # pytest suite + fixtures
  pyproject.toml
  uv.lock
```

---

## Adding a new action

1. Create `src/tf_tool/actions/<name>/` (e.g. `registry_search/`).
2. Add `action.py` subclassing `ActionBase` with constants: `ID` (UUID), `NAME`, `DESCRIPTION`, `VERSION`.
3. Colocate logic and validation in the same folder (`validation.py`, `client.py`, etc.).
4. Export from `<name>/__init__.py`.
5. Register in `actions/bootstrap.py` via `register_all_actions()`.

Each action implements:

- `invoke(**kwargs) -> Result[str, AppError]`
- `bind_cli(app) -> Result[None, AppError]`

Registration flows through `action.register(manager)` → `ActionManager.register()`.

---

## Development

```bash
cd .cursor/tools/tf-tool
uv sync --dev
uv run python build/run.py
uv run ruff check
uv run ruff format --check
uv run mypy
uv run pytest
```

See **`.cursor/rules/python/python.mdc`** and **`.cursor/rules/terrafrom.mdc`** for repo-wide Python and Terraform guidance.

---

## Documentation

Agent-oriented guide (TLDR, use cases, help, commands): [`docs/README.md`](docs/README.md).

| Doc section | Covers |
|-------------|--------|
| [TLDR](docs/README.md#tldr) | Install once-liner + common commands |
| [Use cases](docs/README.md#use-cases) | When to list vs search vs download |
| [Help](docs/README.md#help) | `--help` behavior and examples |
| [Agent guide](docs/README.md#cursor-ai-agent-guide) | `--agent-help` card for Cursor AI |
| [Commands](docs/README.md#commands) | Search, list, build reference |

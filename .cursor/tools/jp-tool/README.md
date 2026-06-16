# jp-tool

UV-managed CLI under **`.cursor/tools/jp-tool`**: AWS deployment helpers for Cursor AI agents.

Uses **Typer** for commands, **Pydantic** for ingress validation and configuration schemas, and **`returns`** `Result` for explicit success and failure paths. Each feature is a self-contained **action** under `src/jp_tool/actions/`.

| Section | Topic |
|---------|-------|
| [Getting started](#getting-started) | Install, build, clean, and run |
| [Help](#help) | Standard `-h` / `--help` behavior |
| [Commands](#commands) | UV and jp-tool command reference |
| [Build output](#build-output) | `output/` folder layout |
| [Actions](#actions) | Available subcommands |
| [Deploy pipeline](#deploy-pipeline) | Full and post-deploy flows |
| [Quality gate](#quality-gate) | Automatic ruff checks before run |
| [Configuration](#configuration) | `app_config.toml` and env overrides |
| [Project layout](#project-layout) | Source tree |
| [Development](#development) | Tests and manual quality checks |

---

## Getting started

```bash
cd .cursor/tools/jp-tool
uv sync --dev
```

`uv sync --dev` creates `.venv`, installs runtime dependencies, and dev tools (ruff, mypy, pytest).

**Typical workflow:**

```bash
uv run jp-tool-build          # build package into output/
uv run jp-tool-install        # link jp-tool into ~/.local/bin (on PATH)
jp-tool --help                # run from any directory
jp-tool deploy --yes
uv run jp-tool-clean          # remove build artifacts when done
```

One-time setup to run `jp-tool` from any terminal:

```bash
cd .cursor/tools/jp-tool
uv sync --dev
uv run jp-tool-build
uv run jp-tool-install
```

`jp-tool-install` symlinks `output/bin/jp-tool` into `~/.local/bin`. Override with `JP_TOOL_INSTALL_DIR=/path/to/bin`.

---

## Help

Standard CLI help (Typer/Click conventions):

| Invocation | Output | Exit code |
|------------|--------|-----------|
| `uv run jp-tool --help` | Full help on stdout | `0` |
| `uv run jp-tool -h` | Same as `--help` | `0` |
| `uv run jp-tool` | Help when no subcommand | `2` |
| `uv run jp-tool <command> --help` | Subcommand help | `0` |

```bash
uv run jp-tool --help
uv run jp-tool deploy --help
```

Help requests **skip the ruff quality gate** so usage is always available.

**Cursor AI agents** should run `jp-tool --agent-help` (or `jp-tool agent-guide`) first — a structured guide card with use cases, commands, and expected output examples.

---

## Commands

| Command | What it does |
|---------|----------------|
| `uv sync --dev` | Install dependencies into `.venv` |
| `uv run jp-tool-build` | Build package into `output/` (does not run the app) |
| `uv run jp-tool-clean` | Remove `output/`, caches, and build artifacts |
| `uv run python build/package.py` | Same as `jp-tool-build` |
| `uv run python build/clean.py` | Same as `jp-tool-clean` |
| `uv run python build/run.py` | Run ruff quality gate only |
| `uv run jp-tool ...` | Quality gate, then CLI command |
| `uv run pytest` | Run test suite |
| `uv run ruff check` | Lint |
| `uv run ruff format --check` | Format check |
| `uv run mypy` | Type check |

### Environment variables

| Variable | Purpose |
|----------|---------|
| `JP_TOOL_SKIP_BUILD_GATE=1` | Skip automatic ruff gate before CLI (debugging only) |
| `JP_TOOL_SKIP_ENV_CHECK=1` | Skip Python/dependency check before CLI |
| `JP_TOOL_PLAIN=1` | Disable TTY operation UI spinner |

---

## Build output

Build with:

```bash
uv run jp-tool-build
```

After build, **`output/`** contains the application artifacts and runnable launchers:

```
output/
  bin/
    jp-tool                   # executable symlinks (chmod +x targets)
    jp-tool-build
    jp-tool-clean
  venv/                       # isolated runtime with wheel installed
  env.sh                      # exports output/bin onto PATH
  dist/
    jp_tool-<version>-py3-none-any.whl
    jp_tool-<version>.tar.gz
  app/
    jp_tool/                  # extracted application package
    jp_tool-<version>.dist-info/
```

Run from any directory after build:

```bash
source .cursor/tools/jp-tool/output/env.sh   # once per shell session
jp-tool --help
jp-tool deploy --yes
```

Clean with:

```bash
uv run jp-tool-clean
```

---

## Actions

### Run examples

```bash
uv run jp-tool --help
uv run jp-tool doctor
uv run jp-tool deploy --yes
uv run jp-tool post-deploy --yes --skip-build
```

Module entry (equivalent):

```bash
uv run python -m jp_tool
uv run python -m jp_tool doctor
uv run python -m jp_tool deploy --yes
```

### `doctor` / `env-check`

Validate Python version and runtime dependencies. Emits JSON on stdout.

### `deploy`

Full pipeline: configure → preflight → terraform → build → ECR → Helm → validate.

### `post-deploy`

Skip Terraform; run build/ECR/Helm/validate after a prior apply.

---

## Deploy pipeline

| Flag | Purpose |
|------|---------|
| `--yes` | Auto-approve terraform apply |
| `--skip-build` | Skip Docker image build |
| `--skip-scaffold` | Skip secrets scaffold phase |
| `--skip-preflight` | Skip tool and AWS preflight checks |
| `--image-tag` | Override container image tag |
| `--no-cache` | Build Docker images without cache |

```bash
jp-tool deploy --yes
jp-tool deploy --yes --skip-preflight --image-tag v1.2.3
jp-tool post-deploy --yes --skip-build
```

Requires AWS CLI profile and external tools (terraform, docker, kubectl, helm) — see preflight phase.

---

## Quality gate

Every `jp-tool` run (except `--help` / `-h` / `--agent-help`) executes the **ruff quality gate** first:

1. `ruff check src testing`
2. `ruff format --check src testing`

If either fails, the CLI exits before any action runs. This is separate from `uv run jp-tool-build`.

```bash
uv run python build/run.py    # manual gate only
uv run jp-tool ...            # gate, then command
```

---

## Configuration

Runtime config lives in **`app_config.toml`** beside `pyproject.toml` (PascalCase sections).

**Precedence:** defaults → `app_config.toml` → **environment variables** (`JP_TOOL_<SECTION>_<FIELD>`).

```toml
[App]
Env = "dev"

[Aws]
Profile = "kt-acc"
Region = "us-east-1"
```

See **`.cursor/rules/constants/constants.mdc`** for canonical AWS profile and account values.

---

## Project layout

```
.cursor/tools/jp-tool/
  build/                    # manual script entrypoints (run, clean, package)
  card.md                   # agent job card
  output/                   # build artifacts (gitignored)
  src/jp_tool/
    actions/                # one subfolder per action
      deploy/
      doctor/
    action_manager/
    build/                  # gate, cleanup, package logic
    core/
    deploy/                 # pipeline phases and orchestration
    cli.py
  testing/                  # pytest suite
  app_config.toml           # runtime deploy configuration
  pyproject.toml
  uv.lock
```

---

## Development

```bash
cd .cursor/tools/jp-tool
uv sync --dev
uv run python build/run.py
uv run ruff check
uv run ruff format --check
uv run mypy
uv run pytest
```

See **`.cursor/rules/python/python.mdc`** and **`.cursor/rules/infras/aws.mdc`** for repo-wide Python and AWS guidance.

---

## Related

| Topic | Path |
|-------|------|
| Tooling index | `.cursor/rules/tool/tool.mdc` |
| Project constants | `.cursor/rules/constants/constants.mdc` |
| Terraform root | `infra/aws/aws_tf/` |
| Container deploy overview | `infra/aws/containers/README.md` |

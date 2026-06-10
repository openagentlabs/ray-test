---
name: aspire-registry-tool
description: >-
  Arb Aspire service registry: add/list/remove rows in service-registry.sqlite and
  emit the AI tool manifest via the uv-managed CLI under .cursor/tools/aspire.
  Use when the user works under aspire.svc/ or asks about registered booter services,
  ASPIRE_REGISTRY_DB, or aspire-tool.
---

# Aspire registry tool (canonical)

## Location

- **CLI package**: **`.cursor/tools/aspire/`** (run all `uv` / `pytest` commands from this directory).
- **Default database**: **`aspire.svc/service-registry.sqlite`** relative to the **process current working directory**, unless **`ASPIRE_REGISTRY_DB`** is set to an absolute path.

## Setup

```bash
cd .cursor/tools/aspire
uv sync
```

## Commands

```bash
uv run aspire-tool              # JSON tool manifest (no flags)
uv run aspire-tool -l           # list services as JSON
uv run aspire-tool -a -p /path/to/bin -n "My Service" -d "Desc"
uv run aspire-tool -r -i <row_id>
```

## Working directory

Prefer **repository root** as **cwd** when running the tool so the default SQLite path resolves to **`./aspire.svc/service-registry.sqlite`**. If cwd is elsewhere, set **`ASPIRE_REGISTRY_DB`** to **`$REPO_ROOT/aspire.svc/service-registry.sqlite`**.

## Quality and tests

- Follow **repository root** **`.cursor/rules/python.mdc`** and **`.cursor/rules/testing_py.mdc`** for pytest layout and typing expectations.
- Run tests: **`cd .cursor/tools/aspire && uv run pytest`**.

## Rules alignment

- **Monorepo layout / ports**: **`.cursor/rules/solution.mdc`** (repository root).
- **Arb Aspire app code**: **`aspire.svc/.cursor/rules/`** — do not fold registry schema changes into unrelated Next.js UI rules.

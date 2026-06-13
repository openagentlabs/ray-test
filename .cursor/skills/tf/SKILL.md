---
name: tf
description: >-
  Terraform CLI workflows from infra/aws/aws_tf plus tf-tool registry CLI
  (.cursor/tools/tf-tool). Run tf-tool via uv run; doctor validates Python and
  deps. Progressive disclosure: SKILL.md, workflow.md, reference.md, card.md.
  Use when user names tf/terraform, registry search, plan/validate/apply infra.
disable-model-invocation: false
---

# tf — Terraform skill

Path: **`.cursor/skills/tf/`**

## What · When · How

**What:** (1) **Terraform CLI** — fmt, validate, plan, apply, Checkov from **`infra/aws/aws_tf`**. (2) **`tf-tool`** — public Registry search/list (`.cursor/tools/tf-tool`).

**When:** User names **`tf`** / **`terraform`**, asks **fmt/validate/plan/apply/test** infra, **registry modules**, finishes **`infra/**`** edits.

**How:** Terraform → **[workflow.md](workflow.md)**. tf-tool → **uv run** + **[card.md](../../tools/tf-tool/card.md)** (one job). Shell syntax → **[reference.md](reference.md)** on **RUN** only.

---

## tf-tool (companion CLI)

| Field | Value |
|-------|--------|
| **Location** | **`.cursor/tools/tf-tool/`** |
| **Run (mandatory for agents)** | `cd .cursor/tools/tf-tool && uv run tf-tool <command>` |
| **Job card** | **[card.md](../../tools/tf-tool/card.md)** |
| **Env validation** | `uv run tf-tool doctor` (alias `env-check`) — see below |
| **Live guide** | `uv run tf-tool --agent-help` |

### Run with uv

```bash
cd .cursor/tools/tf-tool
uv sync --dev                    # once, or after lockfile / dependency changes
uv run tf-tool doctor            # FIRST: environment check (mandatory)
uv run tf-tool search-aws -q vpc --limit 5
uv run tf-tool list-aws --limit 5 --json
```

**First action when skill is invoked (tf-tool path):** run **`uv run tf-tool doctor`** or any command — environment check runs automatically with a **spinner** (blue operation label), then captured output replays below in **green** (results), **red** (errors), or **yellow** (warnings). A **summary table** prints at session end. JSON for agents stays on **stdout**; UI renders on **stderr**. Disable UI: `TF_TOOL_PLAIN=1`.

| Step | Command | Notes |
|------|---------|--------|
| Sync | `uv sync --dev` | Creates `.venv`, installs locked runtime + dev deps |
| Doctor | `uv run tf-tool doctor` | Before first tf-tool use in session |
| Job | `uv run tf-tool <cmd> …` | Match one **JOB-*** in **[card.md](../../tools/tf-tool/card.md)** |
| PATH (optional) | `uv run tf-tool-build && uv run tf-tool-install` | Then `tf-tool` globally; still run `doctor` after sync |

**Do not** use system `python` or a bare `tf-tool` on PATH without **`doctor`** confirming the active environment.

### Environment validation (`doctor`)

tf-tool **automatically** checks before every command (except `--help`, `--agent-help`, `doctor`):

- **Python** — `requires-python` from `pyproject.toml` (or wheel metadata)
- **Dependencies** — each runtime dep (`httpx`, `pydantic`, `returns`, `rich`, `typer`): installed version must satisfy the declared specifier **and** import successfully

Explicit report:

```bash
cd .cursor/tools/tf-tool && uv run tf-tool doctor
```

| Exit | Meaning | Fix |
|------|---------|-----|
| 0 | `"ok": true` in JSON stdout | Proceed |
| 2 | `"error": "environment"` | `uv sync --dev`; re-run `doctor` |

Skip auto-check (debug only): `TF_TOOL_SKIP_ENV_CHECK=1`.

### Job card usage

1. **Doctor** → **JOB-01a** in **[card.md](../../tools/tf-tool/card.md)**
2. **Intent** → read **one JOB-*** only
3. **Run** with **`uv run tf-tool …`**
4. List commands in automation → **`--json`** (JOB-13+)

---

## Progressive disclosure (mandatory)

| File | Read when |
|------|-----------|
| **`SKILL.md`** | Skill invoked |
| **[card.md](../../tools/tf-tool/card.md)** | Invoking tf-tool (one job) |
| **[workflow.md](workflow.md)** | Executing Terraform CLI workflow |
| **[reference.md](reference.md)** | Workflow **RUN** needs commands |
| **[workflow-reference.md](../workflow-reference.md)** | Unclear on **`Jmp:`** / **`Delay:`** |

Never preload **card.md**, **reference.md**, or **workflow-reference.md** at skill start.

---

## Mandatory rules (before shell or edits)

1. **tf-tool first** — On skill invoke for registry work: `cd .cursor/tools/tf-tool`; **`uv sync --dev`** if needed; **`uv run tf-tool doctor`** (or any command — env check runs first with spinner UI). On fail → sync and retry. Plain/CI: `TF_TOOL_PLAIN=1`.
2. **Surface** — Registry → tf-tool + **[card.md](../../tools/tf-tool/card.md)**. Plan/apply → **workflow.md** + **reference.md** on **RUN**.
3. **Tf workflow** — **workflow.md**; **`WorkflowStart:`** → **`WorkflowEnd:`** unless **`Jmp:`**.
4. **TF root** — **`infra/aws/aws_tf/`**; **AWS_*** + pre-flight per **infra.mdc**.
5. **Apply/destroy** — Same-turn explicit yes.
6. **Checkov** — Before apply or end of **`infra/`** session.
7. **Handoff** — What ran, pass/fail, next step.

---

## Related

| Topic | Path |
|-------|------|
| **tf-tool job card** | **[card.md](../../tools/tf-tool/card.md)** |
| tf-tool source | **`.cursor/tools/tf-tool/`** |
| Tf workflow | **[workflow.md](workflow.md)** |
| Terraform CLI | **[reference.md](reference.md)** |
| HCL | **`.cursor/rules/iac/terrafrom.mdc`** |

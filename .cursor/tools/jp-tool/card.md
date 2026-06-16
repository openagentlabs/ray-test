# jp-tool — job card

> **Read policy:** Open **only** when you need to **invoke jp-tool** (AWS deploy pipeline). For **Terraform registry search**, use **tf-tool** (`.cursor/tools/tf-tool/card.md`) instead. Read **one job** matching your intent; do not preload the whole file.

**Tool path (repo root):** `.cursor/tools/jp-tool/`  
**Run (preferred):** `cd .cursor/tools/jp-tool && uv run jp-tool <command>`  
**Binary on PATH:** `jp-tool` (optional after [install](#job-00-install))  
**Auth:** AWS CLI profile per `app_config.toml` / `.cursor/rules/constants/constants.mdc`  
**Env check:** runs automatically before every command. Explicit: [JOB-01a](#job-01a-environment-doctor).  
**Operation UI (TTY):** blue spinner + operation label → green/red/yellow replay on stderr → summary table at end. Disable: `JP_TOOL_PLAIN=1`.

---

## JOB-00: Install and sync (one-time / after lockfile change)

| Field | Value |
|-------|--------|
| **When** | First use, missing deps, or `doctor` fails |
| **Command** | `cd .cursor/tools/jp-tool && uv sync --dev` |
| **Optional PATH install** | `uv run jp-tool-build && uv run jp-tool-install` |
| **Verify** | `uv run jp-tool doctor` |
| **Exit** | 0 on success |
| **Output** | `.venv` with locked deps; `doctor` JSON with `"ok": true` |

**Agents:** always run via **`uv run jp-tool …`** from **`.cursor/tools/jp-tool`** unless a global `jp-tool` on PATH is verified with `doctor`.

---

## JOB-01a: Environment doctor

| Field | Value |
|-------|--------|
| **When** | Before first jp-tool use in a session; after `uv sync`; when imports fail |
| **Command** | `cd .cursor/tools/jp-tool && uv run jp-tool doctor` |
| **Alias** | `uv run jp-tool env-check` |
| **Exit** | 0 pass · 2 fail |
| **Output (stdout, JSON)** | Python + each runtime dependency with installed version vs required specifier |

---

## JOB-01: Agent guide (live card)

| Field | Value |
|-------|--------|
| **When** | First use in session or output shape unclear |
| **Command** | `jp-tool --agent-help` |
| **Alternates** | `jp-tool agent-guide` · `jp-tool agent-help` |
| **Flags** | Do **not** combine with another subcommand |
| **Exit** | 0 |
| **Output** | Plain-text guide on **stdout**; build gate skipped |

---

## JOB-02: Full deploy pipeline

| Field | Value |
|-------|--------|
| **When** | End-to-end AWS deploy (Terraform → build → ECR → Helm) |
| **Command** | `jp-tool deploy --yes` |
| **Parameters** | `--skip-build`, `--skip-scaffold`, `--skip-preflight`, `--image-tag`, `--no-cache` |
| **Exit** | 0 success · 2 validation/build |
| **Output (stdout, text)** | Phase summary on success |

---

## JOB-03: Post-deploy rollout

| Field | Value |
|-------|--------|
| **When** | Terraform already applied; run build/ECR/Helm/validate only |
| **Command** | `jp-tool post-deploy --yes` |
| **Parameters** | Same flags as JOB-02 |
| **Exit** | 0 success · 2 validation/build |

---

## Decision quick pick

| Need | Job |
|------|-----|
| Sync / install | JOB-00 |
| Validate Python + deps | JOB-01a |
| Full AWS deploy | JOB-02 |
| Post-Terraform rollout | JOB-03 |
| Live agent guide | JOB-01 |

**Not supported:** Terraform registry search (use tf-tool), ad-hoc `terraform plan` without deploy orchestration.

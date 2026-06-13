---
name: prj
description: >-
  Interactive project constants skill: init (PRJ_*), quick init, show current
  values, and help listing capabilities. Reads and writes Group 1 in
  .cursor/rules/constants.mdc one constant at a time with validation. Use when
  the user names prj, project init, prj help, prj show, or PRJ_NAME/PRJ_SLUG.
disable-model-invocation: false
---

# prj — project constants skill

Path: **`.cursor/skills/prj/`**

## What · When · How

**What:** Guided **project init** — read **Group 1 — Project (`PRJ_*`)** from **`.cursor/rules/constants.mdc`**, collect new values **one constant per turn**, validate format/constraints, sync derived literals, write back to **`constants.mdc`**.

**When:** User names **`prj`**, asks for **`prj help`**, **`prj init`**, **`prj show`**, **`project init`**, or wants to view/configure **`PRJ_*`** constants.

**How:** Match user intent to a **capability** below → run **[workflow.md](workflow.md)** from **`WorkflowStart:`** → **`WorkflowEnd:`**. Validation and patch rules → **[reference.md](reference.md)** (read cited sections only).

---

## Capabilities

The skill exposes **four capabilities**. The agent must route the user to exactly one per invocation (unless the user asks **`prj help`**, which only lists capabilities).

| # | Capability | What it does | How to ask the agent |
|---|------------|--------------|----------------------|
| 1 | **`init`** | Full guided init — all six **`PRJ_*`** constants, **one question per turn**, validate, recap, write **`constants.mdc`** | `prj init`, **`init project constants`**, **`configure project constants`**, **`set PRJ_NAME`**, **`rename project`** |
| 2 | **`init-quick`** | Same as **`init`**; user may reply **`keep`** on any constant to retain the current value | `prj init --quick`, **`quick project init`**, **`prj init quick`** |
| 3 | **`help`** | List all capabilities (this table) and example phrases — **no file changes** | `prj help`, **`what can prj do?`**, **`prj capabilities`**, **`how do I use the prj skill?`** |
| 4 | **`show`** | Read-only table of current Group 1 values from **`constants.mdc`** — **no writes** | `prj show`, **`show project constants`**, **`what are the PRJ_* values?`**, **`list project constants`** |

**Default:** If the user says only **`prj`** with no capability → run **`help`** first, then wait for their choice.

**Capability order in docs and help output:** always **`init`** → **`init-quick`** → **`help`** → **`show`** ( **`show`** is last).

---

## Progressive disclosure (mandatory)

| File | Read when |
|------|-----------|
| **`SKILL.md`** | Skill invoked |
| **[workflow.md](workflow.md)** | Executing any capability except **`help`** (help uses § Capabilities above only) |
| **[reference.md](reference.md)** | **VALIDATE**, **PATCH**, or **ON_ERROR** for a specific `PRJ_*` id |
| **[workflow-reference.md](../workflow-reference.md)** | Unclear on **`Jmp:`** / **`ASK`** semantics |

Never preload **reference.md** at skill start.

---

## Mandatory rules (before questions or edits)

1. **Single source** — Read and write **only** **`.cursor/rules/constants.mdc`** for catalog values; do not duplicate literals in other rules during this skill.
2. **One question per turn** — During **`WorkflowCollect*:`** stages, **ASK** exactly **one** `PRJ_*` constant; wait for the user reply before the next constant.
3. **Show current default** — Every question must display the **current value** from **`constants.mdc`**, plus **Use**, **Format / constraints** from the constant row (see **[reference.md](reference.md#question-template)**).
4. **Validate before advance** — Apply rules in **[reference.md § Validation](reference.md#validation-by-constant-id)**; on failure, explain why and **Jmp** back to the same collect stage — do not skip validation.
5. **Cross-check slug ↔ package** — After `PRJ_SLUG` and `PRJ_PACKAGE` are both set, run **[reference.md § Cross-validation](reference.md#cross-validation)** before write.
6. **Derived sync** — After all inputs accepted, run **`WorkflowSyncDerived:`** so literals that must equal `PRJ_*` (e.g. **`NET_EKS_CLUSTER_NAME`**) stay consistent — see **[reference.md § Derived updates](reference.md#derived-updates)**.
7. **Confirm before write** — Present recap table (old → new); require explicit **`yes`** before **`WorkflowWriteConstants:`**.
8. **No commit** — Do not git commit unless the user explicitly asks.
9. **Handoff** — After **`WorkflowEnd:`**, summarize what changed and remind that **`terraform.tfvars`** / app package names may need a follow-up sync per **constants.mdc** Rules §4.

---

## Scope

| In scope | Out of scope |
|----------|----------------|
| **`PRJ_NAME`**, **`PRJ_SLUG`**, **`PRJ_PACKAGE`**, **`PRJ_DESCRIPTION`**, **`PRJ_VERSION`**, **`PRJ_RELEASE_DATE`** | `AWS_*`, `DEP_*`, `NET_*`, `TAG_*` groups (separate future workflow) |
| Derived literals in **`constants.mdc`** that must track `PRJ_*` | Editing **`infra/aws/aws_tf/terraform.tfvars`** unless user asks after handoff |
| **`show`** capability (read-only) | Renaming deployed AWS resources in live account |
| **`help`** capability (list + ask phrases) | — |

---

## Related

| Topic | Path |
|-------|------|
| Constants catalog | **`.cursor/rules/constants.mdc`** |
| Init workflow | **[workflow.md](workflow.md)** |
| Validation & patch | **[reference.md](reference.md)** |
| Physical naming | **`.cursor/rules/infras/resource-naming.mdc`** |
| Workflow DSL | **[workflow-reference.md](../workflow-reference.md)** |

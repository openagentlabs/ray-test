# Workflow reference (generic — all skills)

> **Read policy:** Open this file **only** when you are unsure how **`WorkflowStart:`**, **`Jmp:`**, **`Delay:`**, or stage verbs work. If the skill’s **`SKILL.md`** and its **`workflow.md`** are clear, **do not read this file**.

---

## What it is

A **linear, labeled workflow** format used by repo skills. Each skill defines its **own** workflow in **`workflow.md`** (or equivalent). This document explains the **shared DSL** — not any skill’s real steps.

## How it works

1. Every workflow is bounded by **`WorkflowStart:`** (entry) and **`WorkflowEnd:`** (exit).
2. Between them are **stages**: labels ending with **`:`** (e.g. **`WorkflowPreflight:`**).
3. Each stage lists actions (**RUN**, **ASK**, **IF**, **ON_ERROR**, **STORE**, **NEXT**).
4. Default flow is **forward** stage to stage. **`Jmp: <Label>`** jumps to another label, then continues forward from there.
5. **`Delay: <n>s`** or **`Delay: <n>m`** pauses before the next action (retries, propagation).
6. **Consent gates** (apply, destroy, overwrite) must not be **`Jmp`**’d past without user approval in the same turn.

## How to use it (agents)

1. Read the skill’s **`SKILL.md`** first — it holds what/when/how and tf/skill-specific rules.
2. When **executing** that skill’s workflow, read **that skill’s `workflow.md`** — not this file’s example.
3. When a stage says **RUN** and you need exact shell syntax, read that skill’s **`reference.md`** at the linked section — **only that section**.
4. Read **this file** only if DSL semantics are ambiguous.

### DSL tokens

| Token | Meaning |
|-------|---------|
| **`WorkflowStart:`** / **`WorkflowEnd:`** | Workflow entry / exit |
| **`Workflow<Name>:`** | Named stage |
| **`Jmp: <Label>`** | Jump to label; continue forward |
| **`Delay: <n>s` / `<n>m`** | Wait (seconds / minutes) |
| **RUN** | Shell command — see skill **`reference.md`** |
| **ASK** | One atomic user question |
| **IF / ON_ERROR** | Branch or retry; follow **`Jmp:`** if given |
| **STORE** | Persist named values for later stages |
| **→** | Default next stage when no **`Jmp:`** |

### Generic mandatory rules (all workflow skills)

1. Read the skill **`SKILL.md`** mandatory section before shell or edits.
2. Execute **`WorkflowStart:`** through **`WorkflowEnd:`** in order; skip a stage only via an explicit **`Jmp:`** in that workflow.
3. Never **`Jmp`** past consent gates.
4. Do not guess **RUN** commands — open **`reference.md`** for the cited section only.
5. After **`WorkflowEnd:`**, hand off: what ran, pass/fail, next step.

---

## EXAMPLE ONLY — sample workflow map (do not execute)

> **Not a real skill.** Illustrates structure only. For Terraform, use **[tf/workflow.md](tf/workflow.md)**. For rules authoring, use **[rules-create/SKILL.md](rules-create/SKILL.md)**.

| Stage | Do | Branch / Jmp |
|-------|----|--------------|
| **`WorkflowStart:`** | Load intent. **STORE:** `intent`, `done=false` | → **`WorkflowValidateInput:`** |
| **`WorkflowValidateInput:`** | Check required params. **ON_ERROR** → **`Jmp: WorkflowStart`** | → **`WorkflowExecute:`** |
| **`WorkflowExecute:`** | **RUN:** see skill reference § example | → **`WorkflowHandoff:`** |
| **`WorkflowHandoff:`** | Summarize results | → **`WorkflowEnd:`** |
| **`WorkflowEnd:`** | **STOP** | |

**Example fragment (stage syntax):**

```text
WorkflowExecute:
- RUN: example-command → reference.md#example
- ON_ERROR lock: Delay: 10s; Jmp: WorkflowExecute
- POSTCONDITION: exit 0
```

---

## Related

| Artifact | Path (from repo root) | Relative from this file |
|----------|----------------------|-------------------------|
| Terraform skill entry | `.cursor/skills/tf/SKILL.md` | [tf/SKILL.md](tf/SKILL.md) |
| Terraform workflow (real) | `.cursor/skills/tf/workflow.md` | [tf/workflow.md](tf/workflow.md) |
| Terraform commands | `.cursor/skills/tf/reference.md` | [tf/reference.md](tf/reference.md) |
| tf-tool job card | `.cursor/tools/tf-tool/card.md` | [../tools/tf-tool/card.md](../tools/tf-tool/card.md) |
| tf-tool source | `.cursor/tools/tf-tool/` | [../tools/tf-tool/](../tools/tf-tool/) |

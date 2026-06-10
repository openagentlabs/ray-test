---
name: rules-create
description: >-
  Guided creation of Cursor .mdc rule files: copy .cursor/templates/rule.mdc.tmpl
  into .cursor/rules/, collect purpose and rules one at a time from the user,
  finalize concise agent-oriented content, and output only the completion table per
  .cursor/rules/rule.mdc. Use when the user asks to create a Cursor rule, names
  rules-create / rules_create, or wants interactive rule authoring.
disable-model-invocation: false
---

# rules-create — Cursor rule authoring

## AI agent operating rules (MANDATORY — read first)

You **must** follow every bullet before and during the workflow. **Do not skip any step or section** except via an explicit **`JMP`** / **`GOTO`** in this file, a documented **`ON_ERROR`** / **`ON_<condition>`** branch, or an unrecoverable tool error (report and stop).

1. **Obey `.cursor/rules/rule.mdc`** — template path, single-word filename, one-rule-per-turn intake, finalize pass, and **table-only** completion output.
2. **Execute the workflow in order** from `STEP_1_SCAFFOLD` through `STEP_8_HANDOFF`. Do not reorder steps.
3. **One atomic question per turn** during intake (one parameter or one rule body per message unless confirming a recap).
4. **Never invent** `rule_purpose`, `rule_name`, `always_apply`, `globs`, or rule text — ask or infer only when the conversation already stated it unambiguously; otherwise ask.
5. **Copy the template** — read **`.cursor/templates/rule.mdc.tmpl`** before writing; do not invent frontmatter structure.
6. **Validate `rule_name`** before scaffold: single token, lowercase letters/digits only, length 2–32, matches `^[a-z][a-z0-9]*$`, not reserved (`rule`, `constants`, `solution`). Target path: **`.cursor/rules/<rule_name>.mdc`** must not exist unless the user explicitly approves overwrite.
7. **Rules loop** — collect `rule_text` one at a time until the user replies **`finished`** (case-insensitive). After each rule, ask: **“Next rule, or `finished`?”**
8. **Finalize** — tighten **What / When / How**, frontmatter, and **## Rules**; remove comments and `REPLACE_ME`; link **`.cursor/rules/constants.mdc`** instead of copying constants.
9. **Handoff** — output **only** the completion table from **`.cursor/rules/rule.mdc`** (section **Handoff to the user**). No extra narrative.

---

## What this skill is

Interactive workflow that creates one **`.cursor/rules/<rule_name>.mdc`** file from **`.cursor/templates/rule.mdc.tmpl`**, with user-driven purpose and rules.

## When to use it

- User asks to **create**, **add**, or **scaffold** a Cursor rule or `.mdc` convention file.
- User names **`rules-create`**, **`rules_create`**, or “create rule using the template”.
- User is following **`.cursor/rules/rule.mdc`** and wants guided intake.

## How to use it

Read **AI agent operating rules** above, then run **Workflow** steps sequentially. Store answers in the **Parameters** map; persist to disk at **`STEP_6_WRITE_FILE`** (or update through finalize at **`STEP_7_FINALIZE`**).

---

## Parameters

| Parameter | Type | Required | Set in step | Description |
|-----------|------|----------|-------------|-------------|
| `rule_purpose` | string | yes | STEP_2 | Why the rule exists; drives What/When/How body text |
| `rule_name` | string | yes | STEP_1 | Single lowercase word; filename `<rule_name>.mdc` |
| `rule_title` | string | yes | STEP_3 | Human-readable H1 (may title-case words from purpose) |
| `always_apply` | boolean | yes | STEP_4 | Maps to frontmatter `alwaysApply` |
| `globs` | string[] | if `always_apply` is false | STEP_4 | YAML glob list; omit or empty only if user confirms global manual attach |
| `description` | string | yes | STEP_3 | One-sentence frontmatter `description` for rule picker |
| `what_agent` | string | yes | STEP_3 | **What this file is** paragraph |
| `when_use` | string | yes | STEP_3 | **When to use it** paragraph |
| `how_use` | string | yes | STEP_3 | **How to use it** paragraph |
| `rules_list` | string[] | yes (≥1) | STEP_5 | Actionable rules appended under **## Rules** |
| `overwrite_ok` | boolean | no | STEP_1 | User approved replacing existing `<rule_name>.mdc` |

---

## Workflow

### STEP_1_SCAFFOLD — name and path

- **ASK**: “What should the rule file be called? Use a **single lowercase word** (e.g. `grpc`, `logging`, `validation`).”
- **VALIDATE**: `rule_name` matches `^[a-z][a-z0-9]*$`, length 2–32, not reserved; path **`.cursor/rules/<rule_name>.mdc`**.
- **IF** file exists and `overwrite_ok` is not true: ask overwrite yes/no; on no, **JMP STEP_1_SCAFFOLD**.
- **ACTION**: Read template; prepare write path (defer disk write until STEP_6 unless user asked to scaffold early).
- **POSTCONDITION**: `rule_name` stored.

### STEP_2_INPUT_PURPOSE

- **ASK**: “In one or two sentences, what is this rule file for? (Audience, scope, what it should enforce or teach.)”
- **VALIDATE**: non-empty, ≤ 500 chars.
- **ON_ERROR**: **JMP STEP_2_INPUT_PURPOSE**.
- **STORE**: `rule_purpose`.

### STEP_3_DRAFT_METADATA_AND_GUIDE

- **ACTION**: From `rule_purpose`, draft `rule_title`, `description`, `what_agent`, `when_use`, `how_use`. Present a short recap; ask: “Accept as-is? (`yes` / `no` — if no, tell me what to change.)”
- **ON `no`**: apply user corrections; **JMP STEP_3_DRAFT_METADATA_AND_GUIDE** until `yes`.
- **POSTCONDITION**: all STEP_3 strings stored.

### STEP_4_SCOPE

- **ASK**: “Should this rule **always apply** to every session? (`yes` / `no`)" 
- **VALIDATE**: maps to `always_apply` true/false.
- **IF** `always_apply` is false: **ASK** for glob patterns (comma-separated or one per line). Parse into `globs` list.
- **ON_ERROR**: **JMP STEP_4_SCOPE**.
- **STORE**: `always_apply`, `globs`.

### STEP_5_COLLECT_RULES

- **ASK**: “Rule 1: What is the first concrete rule? (One actionable requirement.)”
- **VALIDATE**: non-empty, ≤ 400 chars per rule.
- **APPEND** to `rules_list`.
- **ASK**: “Next rule, or `finished`?”
- **ON** next rule: loop with incrementing label (Rule 2, Rule 3, …).
- **ON** `finished`: require `rules_list.length >= 1`; else **JMP STEP_5_COLLECT_RULES**.
- **POSTCONDITION**: `rules_list` complete.

### STEP_6_WRITE_FILE

- **ACTION**: Copy template to **`.cursor/rules/<rule_name>.mdc`**; set frontmatter (`description`, `alwaysApply`, optional `globs`); fill What/When/How; render **## Rules** as numbered or bulleted list from `rules_list`; remove template comments and `REPLACE_ME`.
- **ON_ERROR** (write failure): report path and error; stop (no JMP unless user fixes path).

### STEP_7_FINALIZE

- **ACTION**: Re-read file; shorten; dedupe; ensure links to **constants.mdc** / **solution.mdc** where appropriate; line-count sanity (~80 lines target).
- **POSTCONDITION**: file ready for commit by user (do not commit unless asked).

### STEP_8_HANDOFF

- **ACTION**: Emit **only** the completion table per **`.cursor/rules/rule.mdc`** with accurate totals.
- **POSTCONDITION**: user sees file path, agent-view summary, and rule count.

---

## JMP / GOTO labels

| Label | Use |
|-------|-----|
| `STEP_1_SCAFFOLD` | Invalid or duplicate `rule_name` |
| `STEP_2_INPUT_PURPOSE` | Empty purpose |
| `STEP_3_DRAFT_METADATA_AND_GUIDE` | User rejected recap |
| `STEP_4_SCOPE` | Invalid yes/no or globs |
| `STEP_5_COLLECT_RULES` | Empty rule or `finished` with zero rules |

---

## Non-goals

- Do not create rules under **`~/.cursor/skills-cursor/`** (Cursor internal).
- Do not commit or push unless the user explicitly asks.
- Do not output long prose at handoff — **table only**.

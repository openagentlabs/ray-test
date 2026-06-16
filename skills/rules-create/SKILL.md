---
name: rules-create
description: >-
  Guided creation of new Cursor .mdc rule files: copy .cursor/rules/rules/template.mdc
  into .cursor/rules/, collect purpose and typed single-line bullets (Knowledge/Rule/Action),
  and output only the completion table per .cursor/rules/rules/rules.mdc. Use when the user
  asks to create a Cursor rule, names rules-create / rules_create, or wants interactive rule authoring.
  Not for editing existing rules.
disable-model-invocation: false
---

# rules-create — Cursor rule authoring (creation only)

Path: **`skills/rules-create/`** (entry router: **`.cursor/skills/ray-test/SKILL.md`**)

## AI agent operating rules (MANDATORY — read first)

You **must** follow every bullet before and during the workflow. **Do not skip any step or section** except via an explicit **`JMP`** / **`GOTO`** in this file, a documented **`ON_ERROR`** / **`ON_<condition>`** branch, or an unrecoverable tool error (report and stop).

1. **Creation only** — This skill creates **new** `.cursor/rules/**/*.mdc` files only; do not use it for editing existing rules.
2. **Obey `.cursor/rules/rules/rules.mdc`** — three-section layout (**Filters**, **Agent init**, **Rules content**), template path, single-word filename, typed single-line bullets, one-bullet-per-turn intake, finalize pass, and **table-only** completion output.
3. **Execute the workflow in order** from `STEP_1_SCAFFOLD` through `STEP_8_HANDOFF`. Do not reorder steps.
4. **One atomic question per turn** during intake (one parameter or one bullet body per message unless confirming a recap).
5. **Never invent** `rule_purpose`, `rule_name`, `always_apply`, `globs`, or bullet text — ask or infer only when the conversation already stated it unambiguously; otherwise ask.
6. **Copy the template** — read **`.cursor/rules/rules/template.mdc`** before writing; do not invent frontmatter or section structure.
7. **Validate `rule_name`** before scaffold: single token, lowercase letters/digits only, length 2–32, matches `^[a-z][a-z0-9]*$`, not reserved (`rules`, `constants`, `solution`, `template`). Target path must not exist unless the user explicitly approves overwrite.
8. **Intelligent use default** — `alwaysApply: false`; omit `globs` unless the user explicitly requests path filters.
9. **Rules loop** — collect each bullet as one line: `Knowledge:`, `Rule:`, or `Action:` prefix (PascalCase type, no spaces, colon, space, statement) until the user replies **`finished`**. After each bullet, ask: **"Next rule, or `finished`?"**
10. **Finalize** — tighten **Agent init** mandatory opener and bullets, **Rules content** subsections (instruction line + bullets), and frontmatter; remove comments and `REPLACE_ME`; link **`.cursor/rules/constants/constants.mdc`** instead of copying constants.
11. **Handoff** — output **only** the completion table from **`.cursor/rules/rules/rules.mdc`** (Handoff subsection in **Rules content**). No extra narrative.

---

## What this skill is

Interactive workflow that creates one **new** `.cursor/rules/<rule_name>/<rule_name>.mdc` file from **`.cursor/rules/rules/template.mdc`**, with user-driven purpose and typed single-line bullets.

## When to use it

- User asks to **create**, **add**, or **scaffold** a **new** Cursor rule or `.mdc` convention file.
- User names **`rules-create`**, **`rules_create`**, or "create rule using the template".
- User is following **`.cursor/rules/rules/rules.mdc`** and wants guided intake.

## How to use it

Read **AI agent operating rules** above, then run **Workflow** steps sequentially. Store answers in the **Parameters** map; persist to disk at **`STEP_6_WRITE_FILE`** (or update through finalize at **`STEP_7_FINALIZE`**).

---

## Parameters

| Parameter | Type | Required | Set in step | Description |
|-----------|------|----------|-------------|-------------|
| `rule_purpose` | string | yes | STEP_2 | Why the rule exists; drives Agent init and Rules content |
| `rule_name` | string | yes | STEP_1 | Single lowercase word; filename `<rule_name>.mdc` |
| `rule_title` | string | yes | STEP_3 | Human-readable H1 (may title-case words from purpose) |
| `always_apply` | boolean | yes | STEP_4 | Maps to frontmatter `alwaysApply`; default false |
| `globs` | string[] | only if user requests | STEP_4 | YAML glob list; omit by default (intelligent use) |
| `description` | string | yes | STEP_3 | One-sentence frontmatter `description` for rule picker |
| `mandatory_opener` | string | yes | STEP_3 | Single `**Mandatory:**` line for **Agent init** |
| `agent_init_bullets` | string[] | yes | STEP_3 | Typed bullets under **Agent init** |
| `rules_content_sections` | object[] | yes | STEP_5 | Each: `title`, `instruction_line`, `bullets[]` for **Rules content** `###` subsections |
| `overwrite_ok` | boolean | no | STEP_1 | User approved replacing existing target file |

---

## Workflow

### STEP_1_SCAFFOLD — name and path

- **ASK**: "What should the rule file be called? Use a **single lowercase word** (e.g. `grpc`, `logging`, `validation`)."
- **VALIDATE**: `rule_name` matches `^[a-z][a-z0-9]*$`, length 2–32, not reserved; path **`.cursor/rules/<rule_name>/<rule_name>.mdc`** (or grouped subfolder like **`infras/`** if user specifies).
- **IF** file exists and `overwrite_ok` is not true: ask overwrite yes/no; on no, **JMP STEP_1_SCAFFOLD**.
- **ACTION**: Read **`.cursor/rules/rules/template.mdc`**; prepare write path (defer disk write until STEP_6 unless user asked to scaffold early).
- **POSTCONDITION**: `rule_name` stored.

### STEP_2_INPUT_PURPOSE

- **ASK**: "In one or two sentences, what is this rule file for? (Audience, scope, what it should enforce or teach.)"
- **VALIDATE**: non-empty, ≤ 500 chars.
- **ON_ERROR**: **JMP STEP_2_INPUT_PURPOSE**.
- **STORE**: `rule_purpose`.

### STEP_3_DRAFT_METADATA_AND_AGENT_INIT

- **ACTION**: From `rule_purpose`, draft `rule_title`, `description`, `mandatory_opener`, and `agent_init_bullets` (include the required first `Rule:` line about single-line format, plus `Knowledge:` scope/when lines and at least one `Action:`). Present a short recap; ask: "Accept as-is? (`yes` / `no` — if no, tell me what to change.)"
- **ON `no`**: apply user corrections; **JMP STEP_3_DRAFT_METADATA_AND_AGENT_INIT** until `yes`.
- **POSTCONDITION**: all STEP_3 strings stored.

### STEP_4_SCOPE

- **ASK**: "Should this rule **always apply** to every session? (`yes` / `no` — default `no`, intelligent use)"
- **VALIDATE**: maps to `always_apply` true/false.
- **IF** user explicitly requests path filters: **ASK** for glob patterns (comma-separated or one per line). Parse into `globs` list. Otherwise leave `globs` empty/omitted.
- **ON_ERROR**: **JMP STEP_4_SCOPE**.
- **STORE**: `always_apply`, `globs`.

### STEP_5_COLLECT_RULES

- **ASK**: "Rules content subsection title and instruction line (what/when this group applies)."
- **ASK**: "Bullet 1: one line starting with `Knowledge:`, `Rule:`, or `Action:` (see `.cursor/rules/rules/rules.mdc`)."
- **VALIDATE**: non-empty, single line, ≤ 600 chars, starts with `Knowledge:`, `Rule:`, or `Action:`.
- **APPEND** to current subsection `bullets`.
- **ASK**: "Next bullet, next subsection, or `finished`?"
- **ON** `finished`: require at least one subsection with ≥1 bullet; else **JMP STEP_5_COLLECT_RULES**.
- **POSTCONDITION**: `rules_content_sections` complete.

### STEP_6_WRITE_FILE

- **ACTION**: Copy **`.cursor/rules/rules/template.mdc`** to target path; set frontmatter (`description`, `alwaysApply`, optional `globs`); fill H1, **Agent init**, and **Rules content** subsections; remove template placeholders.
- **ON_ERROR** (write failure): report path and error; stop (no JMP unless user fixes path).

### STEP_7_FINALIZE

- **ACTION**: Re-read file; shorten; dedupe; verify every **Rules content** bullet is one typed line; each `###` has one instruction line then bullets; ensure links to **constants.mdc** / **solution.mdc** where appropriate; line-count sanity (~200 lines before split).
- **POSTCONDITION**: file ready for commit by user (do not commit unless asked).

### STEP_8_HANDOFF

- **ACTION**: Emit **only** the completion table per **`.cursor/rules/rules/rules.mdc`** with accurate totals.
- **POSTCONDITION**: user sees file path, section summary, and bullet count.

---

## JMP / GOTO labels

| Label | Use |
|-------|-----|
| `STEP_1_SCAFFOLD` | Invalid or duplicate `rule_name` |
| `STEP_2_INPUT_PURPOSE` | Empty purpose |
| `STEP_3_DRAFT_METADATA_AND_AGENT_INIT` | User rejected recap |
| `STEP_4_SCOPE` | Invalid yes/no or globs |
| `STEP_5_COLLECT_RULES` | Empty bullet, invalid format, or `finished` with zero bullets |

---

## Non-goals

- Do not edit existing rule files under this skill — use normal editing.
- Do not create rules under **`~/.cursor/skills-cursor/`** (Cursor internal).
- Do not commit or push unless the user explicitly asks.
- Do not output long prose at handoff — **table only**.

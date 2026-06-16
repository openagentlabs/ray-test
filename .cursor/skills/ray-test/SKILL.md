---
name: ray-test
description: >-
  Ray Test skills hub — entry point that routes the user to one modular skill
  under skills/ (tf, prj, aws_dynamodb_create, aws_s3_create, rules-create).
  Use when the user names ray-test, skills, asks which skill to use, or wants
  a guided workflow without naming a specific skill. Also use when intent maps
  clearly to a catalog skill and delegation is faster than re-explaining options.
disable-model-invocation: false
---

# ray-test — skills router (entry point)

Path: **`.cursor/skills/ray-test/`** · Catalog: **`skills/catalog.md`** · Skill bodies: **`skills/<id>/`**

## What · When · How

**What:** Interactive **router** — identify the user's goal, match a row in **`skills/catalog.md`**, confirm when ambiguous, then **hand off** by reading and executing **`skills/<id>/SKILL.md`** (and that skill's `workflow.md` / `reference.md` per its own progressive disclosure).

**When:** User says **`ray-test`**, **`skills`**, **`which skill`**, **`help me pick a skill`**, or starts a task that fits a catalog skill but does not name it. Also when user names a catalog ID (`tf`, `prj`, …) — route directly after optional one-line confirm.

**How:** Run the workflow below from **`RouterStart:`** → **`RouterEnd:`**. Never invent a skill not listed in **`skills/catalog.md`**.

---

## AI agent operating rules (mandatory)

1. **Router only until handoff** — Do not run Terraform, edit `constants.mdc`, or scaffold rules while still in router stages. After **`RouterHandoff:`**, obey the **target skill** exclusively.
2. **Catalog is authoritative** — Skill list lives in **`skills/catalog.md`**. Component skills (`aspire.svc/…`) are out of scope unless the user explicitly asks for Aspire pages or registry.
3. **One skill per invocation** — Pick exactly one catalog row unless the user asks for **`list`** / **`catalog`** only.
4. **Progressive disclosure** — Read **`skills/catalog.md`** at router start. Read **`skills/<id>/SKILL.md`** only after **`RouterHandoff:`**. Do not preload target `workflow.md` or `reference.md` during routing.
5. **Numbered choices** — When offering skills, use a **numbered list** matching **`catalog.md`** `#` column. Ask: “Reply with the **number** or **skill id**.”
6. **Direct match shortcut** — If the user message unambiguously maps to one catalog row (e.g. “terraform plan”, “prj init”, “create DynamoDB table”), **`Jmp: RouterConfirm`** with that id pre-selected.
7. **Legacy paths** — If user `@`-mentions **`.cursor/skills/tf/`** etc., treat as the same id under **`skills/`**.

---

## Workflow

### RouterStart:

- **READ** **`skills/catalog.md`**
- **STORE** `catalog_loaded=true`
- **IF** user message matches one catalog row with high confidence → **STORE** `selected_id=<id>` → **`Jmp: RouterConfirm`**
- **ELSE IF** user asked only to list skills → **`Jmp: RouterList`**
- **ELSE** → **`Jmp: RouterAsk`**

### RouterList:

- **PRINT** numbered table from **`skills/catalog.md`** (id, triggers, summary)
- **ASK:** “Which skill? Reply with **number** or **id**, or describe your goal.”
- **NEXT** → **`RouterParse`**

### RouterAsk:

- **ASK:** “What do you want to do? (e.g. Terraform plan, set PRJ_NAME, create DynamoDB, new Cursor rule)”
- **NEXT** → **`RouterParse`**

### RouterParse:

- **MAP** user reply to exactly one `selected_id` from catalog
- **ON_ERROR** ambiguous or no match → explain gap → **`Jmp: RouterList`**
- **NEXT** → **`RouterConfirm`**

### RouterConfirm:

- **ASK:** “Use skill **`{selected_id}`** (`skills/{folder}/`)? Reply **yes** to continue or **no** to pick again.”
- **ON** yes → **`Jmp: RouterHandoff`**
- **ON** no → **`Jmp: RouterList`**
- **ON** user sends new detail that changes intent → **`Jmp: RouterParse`**

### RouterHandoff:

- **READ** **`skills/<folder>/SKILL.md`** where `<folder>` is the catalog **Folder** column (e.g. `skills/tf/SKILL.md`)
- **PRINT** one line: “Handing off to **`{selected_id}`** — following `skills/…/SKILL.md`.”
- **EXECUTE** target skill from its **`WorkflowStart:`** (or equivalent entry) through **`WorkflowEnd:`**
- **NEXT** → **`RouterEnd`**

### RouterEnd:

- **STOP** router behavior; remain in target skill until it completes or user starts a new router request (**`Jmp: RouterStart`**)

---

## Quick id → path map

| User says | Read |
|-----------|------|
| `tf`, terraform | `skills/tf/SKILL.md` |
| `prj`, project constants | `skills/prj/SKILL.md` |
| `aws_dynamodb_create`, DynamoDB | `skills/aws_dynamodb_create/SKILL.md` |
| `aws_s3_create`, S3 | `skills/aws_s3_create/SKILL.md` |
| `rules-create`, new rule | `skills/rules-create/SKILL.md` |

---

## Related

| Topic | Path |
|-------|------|
| Full catalog | **`skills/catalog.md`** |
| Human overview | **`skills/README.md`** |
| Workflow DSL | **`skills/_shared/workflow-reference.md`** |
| Tooling index | **`.cursor/rules/tool/tool.mdc`** |

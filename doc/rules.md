# EXLdecision.AI

## Transform Your Data into Actionable Intelligence

The most comprehensive analytics platform with AI-powered insights, synthetic data generation, and advanced modeling capabilities designed for modern businesses.

<div align="left">

<small>

| | |
|:--|:--|
| **Version** | 1.0.0 |
| **Updated** | 2026-06-14 12:00 UTC |
| **Owner** | platform@example.com |

</small>

</div>

---

# Cursor rules in this solution

This document explains how Cursor rules work in the Ray Test repository. Rules are markdown files (`.mdc`) under `.cursor/rules/`. Cursor loads them into the AI agent context so coding assistance follows project conventions, folder boundaries, naming, and tooling.

If you are new to the repo, read this before adding or editing a rule file.

---

## What rules do here

Rules tell the Cursor agent:

- where code should live (frontend vs microservices vs infra)
- which ports, constants, and naming patterns to use
- how to scaffold docs, Terraform, and new components
- what to avoid (hard-coded AWS values, domain logic in the UI layer, and so on)

Rules are not application runtime config. They are instructions for humans and for the AI when working in this repository.

---

## Where rule files live

```
.cursor/rules/                    # Repo-wide rules (start here)
  constants/constants.mdc        # Project parameter values (single source of truth)
  solution/solution.mdc          # Monorepo layout, ports, component index
  docs/docs.mdc                  # README and documentation policy
  python/python.mdc              # Python conventions
  typescript/typescript.mdc      # TypeScript conventions
  error/error.mdc                # Human-readable errors and logging
  tool/tool.mdc                  # Skills, MCP, and repo CLI index
  infras/                        # AWS naming, tagging, debugging (grouped topics)
  iac/                           # Terraform workflow (grouped topics)
  tools/                         # Repo CLI tools (tf-tool, checkov, etc.)
  rules/
    rules.mdc                    # Meta-policy: how every rule file must be structured
    template.mdc                 # Copy this when creating a new rule file

<service>/.cursor/rules/         # Rules scoped to one app or microservice
  e.g. aspire.svc/.cursor/rules/
  e.g. iam.svc/.cursor/rules/
```

**Single-topic rules** live in **`.cursor/rules/<name>/<name>.mdc`**. **Grouped topics** share a folder (e.g. **`infras/`**, **`iac/`**, **`tools/`**).

**Root vs service rules:** Root `.cursor/rules/` holds cross-cutting guidance. Service folders hold stack-specific detail (gRPC patterns, database rules, logging). Root rules link outward; they do not duplicate per-service content.

**Authoritative meta-policy:** `.cursor/rules/rules/rules.mdc` defines the required shape of every rule file. `.cursor/rules/rules/template.mdc` is the scaffold to copy.

---

## How Cursor picks up a rule

Each rule file starts with YAML frontmatter. This block is called **Filters**. It controls when Cursor attaches the file.

```yaml
---
description: One sentence for the rule picker; what this rule covers.
alwaysApply: false
globs:
  - "infra/**/*.tf"
---
```

| Field | Required | Purpose |
|-------|----------|---------|
| `description` | Yes | Short summary shown in Cursor's rule picker |
| `alwaysApply` | Yes | `true` = loaded every session; `false` = loaded when relevant |
| `globs` | No | File path patterns; rule loads when you work on matching files |

**`alwaysApply: true`** is used for rules that must always be in context, such as `constants.mdc`, `solution.mdc`, and `docs.mdc`.

**`alwaysApply: false` with `globs`** is used for focused rules. Example: `infras/resource-naming.mdc` applies when editing files under `infra/`.

Default for new rules: `alwaysApply: false` and no `globs`, unless the rule must be global or path-specific.

---

## Anatomy of a rule file

Every new rule file has **three sections** in this order. Do not rename or reorder them.

### 1. Filters (YAML frontmatter)

At the very top of the file, between `---` markers. Not markdown. Sets scope only.

### 2. Agent init

Header: `## Agent init`

This is the first section the agent reads after the title. It explains how to read the rest of the file.

Structure:

1. **One mandatory opener line** starting with `**Mandatory:**` and one sentence.
2. **Bullets** below it, each using a typed prefix (see Rule line types below).

The first bullet after the opener must restate that all bullets in **Rules content** are single-line `Knowledge:`, `Rule:`, or `Action:` statements.

Example:

```markdown
## Agent init

**Mandatory:** Read this entire section before any other content in this file; execute every Action line here immediately and retain every Rule and Knowledge line for the rest of this session.

- Rule: Every bullet in Rules content is exactly one line starting with Knowledge:, Rule:, or Action:.
- Knowledge: This file defines gRPC error handling for iam.svc.
- Knowledge: Load this file when adding or changing handlers under iam.svc/server/.
- Action: Read every subsection in Rules content in order before editing code.
```

### 3. Rules content

Header: `## Rules content`

This is where all real guidance lives. It may contain one or more subsections.

Each subsection uses this pattern:

```markdown
### Subsection title

One instruction line (plain prose, not a bullet) saying what this group covers and when to apply it.

- Knowledge: Reference information to remember.
- Rule: A constraint to follow when this file applies.
- Action: A step to run when the condition in the bullet is met.
```

You can add more `###` subsections for separate topics. Each gets its own instruction line and bullet list.

**Tables:** Allowed inside a subsection only after the instruction line and after a `Knowledge:` bullet that introduces the table.

**Avoid `####` nesting.** Prefer another `###` block with its own instruction line.

---

## Rule line types

Every bullet in **Agent init** and **Rules content** is exactly **one line**. Never wrap a rule across multiple lines.

Each line starts with a type prefix, then a colon, then a space, then the statement.

| Prefix | Meaning | Agent behavior |
|--------|---------|----------------|
| `Knowledge:` | Context, definitions, links, table intros | Read and retain |
| `Rule:` | Constraint or policy | Follow when this file applies |
| `Action:` | Executable step | Run when the condition applies; Action lines in Agent init run immediately |

**Format rules for the prefix:**

- PascalCase, no spaces: `Knowledge:`, `Rule:`, `Action:`
- First letter capitalized
- Colon, then one space, then the text

Good:

```
- Rule: Link constants.mdc by constant ID; never paste literal account IDs.
- Knowledge: Dev port for IAM is 8803; see solution.mdc.
- Action: Copy template.mdc before creating a new rule file.
```

Bad:

```
- rule: lowercase prefix
- Rule: This line continues
  on a second line
- Knowledge : extra space before colon
```

---

## How to create a new rule file

### Step 1: Choose location and name

- Path: `.cursor/rules/<name>.mdc` or `.cursor/rules/<subdir>/<name>.mdc`
- Filename: one lowercase word, 2 to 32 characters, letters and digits only (`grpc`, `logging`, `validation`)
- **Reserved names** (do not use outside `.cursor/rules/rules/`): `rules`, `constants`, `solution`, `template`

### Step 2: Copy the template

```bash
cp .cursor/rules/rules/template.mdc .cursor/rules/<name>.mdc
```

Do not invent your own layout.

### Step 3: Fill in Filters

- Write a clear one-sentence `description`
- Set `alwaysApply` (`false` unless the rule must load every session)
- Add `globs` only if the rule should attach to specific file paths

### Step 4: Fill in Agent init

- Keep the mandatory opener; adjust the wording if needed for your topic
- Keep the first `Rule:` bullet about single-line format
- Add `Knowledge:` bullets for what the file is and when to load it
- Add `Action:` bullets for what the agent should do right after reading init

### Step 5: Fill in Rules content

- Add at least one `###` subsection
- Write one instruction line under the heading
- Add `Knowledge:`, `Rule:`, and `Action:` bullets
- Remove every `REPLACE_ME` placeholder before committing

### Step 6: Link, do not copy

If the rule references project name, AWS account, region, deployment key, or ports, link `.cursor/rules/constants/constants.mdc` or `.cursor/rules/solution/solution.mdc` by constant ID or path. Do not paste literal values into multiple files.

### Optional: guided creation

Cursor skill **`skills/rules-create/SKILL.md`** (entry: **`.cursor/skills/ray-test/SKILL.md`**) walks through interactive creation and follows `.cursor/rules/rules/rules.mdc`.

### When to split a file

If a rule file grows past roughly 200 lines, split into a second `.mdc` and add a `Knowledge:` bullet in a Related subsection pointing to the sibling file.

---

## Important rules to know

These files matter most day to day. Several older files still use a previous layout (What/When/How, Format, Build). New and heavily edited files should use the three-section layout from `rules/rules.mdc`.

| File | Loads | What it covers |
|------|-------|----------------|
| `.cursor/rules/rules/rules.mdc` | Always | How rule files must be structured |
| `.cursor/rules/rules/template.mdc` | Never (scaffold only) | Starting point for new rules |
| `.cursor/rules/constants/constants.mdc` | Always | `PRJ_*`, `AWS_*`, `DEP_*`, `NET_*`, `TAG_*` values |
| `.cursor/rules/solution/solution.mdc` | Always | frontend vs `*.svc/`, component table, dev ports 8801-8810 |
| `.cursor/rules/docs/docs.mdc` | Always | README requirements per folder |
| `.cursor/rules/python/python.mdc` | Contextual | Python and async gRPC conventions |
| `.cursor/rules/typescript/typescript.mdc` | Contextual | TypeScript and gRPC client conventions |
| `.cursor/rules/infras/resource-naming.mdc` | `infra/**` | AWS physical names and Terraform labels |
| `.cursor/rules/infras/resource-taging.mdc` | `infra/**` | AWS tag keys and application |
| `.cursor/rules/iac/terrafrom.mdc` | IaC work | Terraform workflow and layout |
| `.cursor/rules/tool/tool.mdc` | `.cursor/tools/**` | Skills, MCP, and repo CLI index |

**Per-service rules:** After picking a component from `solution.mdc`, open that service's `.cursor/rules/` folder for local stack rules.

---

## Quick reference: full file skeleton

```markdown
---
description: One sentence summary.
alwaysApply: false
---

# Human-readable title

## Agent init

**Mandatory:** Read this entire section before any other content in this file; execute every Action line here immediately and retain every Rule and Knowledge line for the rest of this session.

- Rule: Every bullet in Rules content is exactly one line starting with Knowledge:, Rule:, or Action:.
- Rule: Type prefix is PascalCase with no spaces, first letter capitalized, followed by a colon and one space.
- Rule: Knowledge bullets are context to retain; Rule bullets are constraints; Action bullets are steps to execute when their condition applies.
- Knowledge: What this file is.
- Knowledge: When to load this file.
- Action: What to do after reading Rules content.

---

## Rules content

### Topic name

One line describing what this subsection covers and when to apply these bullets.

- Knowledge: Background or reference.
- Rule: Constraint to follow.
- Action: Step when condition is met.
```

---

## Checklist before you commit a new rule

- [ ] Copied from `.cursor/rules/rules/template.mdc`
- [ ] Filters: `description` and `alwaysApply` set; `globs` only if needed
- [ ] Agent init: mandatory opener present; first Rule bullet restates single-line format
- [ ] Rules content: at least one `###` subsection with instruction line and typed bullets
- [ ] No `REPLACE_ME` left in the file
- [ ] Constants and ports linked, not duplicated
- [ ] Filename is one lowercase word and not reserved

---

## Further reading

| Topic | Path |
|-------|------|
| Rule meta-policy (full detail) | `.cursor/rules/rules/rules.mdc` |
| New rule scaffold | `.cursor/rules/rules/template.mdc` |
| Interactive rule creation | **`skills/rules-create/SKILL.md`** · router **`.cursor/skills/ray-test/SKILL.md`** |
| Skills catalog | **`skills/catalog.md`**, **`skills/README.md`** |
| Monorepo layout and ports | `.cursor/rules/solution/solution.mdc` |
| Project parameter catalog | `.cursor/rules/constants/constants.mdc` |

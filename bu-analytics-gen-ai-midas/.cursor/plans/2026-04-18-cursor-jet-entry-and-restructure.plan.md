# Plan: `.cursor` JET entry, consistency, and cleanup (gold standard)

**Status:** Draft for team review  
**Date:** 2026-04-18  
**Scope:** `.cursor/` only (rules, skills, scripts, tools, docs, plans); no Jenkins pipeline tree changes.

---

## 1. Problem statement

Today the workspace already has strong **skills** (for example Jenkins NL → `jenkins_tools.py`) and **rules** (architecture, Jenkins policy). What is missing for operators:

1. A **single named convention** (`jet` + natural language) so everyone phrases requests the same way.
2. A **single short file** agents can load for **first-pass routing** without hard-coding a brittle command grammar.
3. A **documented restructuring and naming policy** so `.cursor/` stays maintainable as the team adds skills and tools.

---

## 2. Target end state

| Layer | Responsibility |
|-------|----------------|
| **JET** (`.cursor/JET.md`) | Optional `jet` keyword; coarse **intent → skill/rule** map; examples; extension rules. Soft binding only. |
| **Skills** (`skills/<id>/SKILL.md`) | Full workflows, trigger phrases, safety gates, step-by-step agent instructions. |
| **Rules** (`rules/*.mdc`) | Always-on or glob-scoped policy (architecture, constants, Jenkins CLI, doc scope). |
| **Tools** (`tools/*` + `tools/readme.md` + `*.TOOL.md`) | Discoverable scripts with Pydantic-style contracts where applicable. |
| **Scripts** (`scripts/*`) | Runnable helpers; documented via `--help` / `scripts/README.md` per `scripts_docs.mdc`. |
| **README** (`.cursor/README.md`) | Newcomer path: what `.cursor` is, how to use JET, where to add things, link to this plan. |

---

## 3. Phased restructure (execute in order)

### Phase A — Entry layer (no moves)

- [x] Add `.cursor/JET.md` as the **canonical** JET contract.
- [ ] Optionally add a **tiny** always-on or agent-requestable rule snippet that says: “When the user prefixes with `jet`, read `.cursor/JET.md` first.” (Team decision: avoid duplication if README + JET are enough.)

### Phase B — Inventory and deduplication

- [ ] Walk `skills/` and list **overlapping** Jenkins/git flows; in README, state **which skill to use when** (one paragraph), pointing to each `SKILL.md` “When to apply” section.
- [ ] Align **git status** items: deleted vs renamed tool docs under `tools/` — pick **one** descriptor naming pattern (`<stem>.TOOL.md`, stem matches script without redundant `-tool` in the descriptor name per `tools/readme.md`).
- [ ] Ensure every tool in `tools/readme.md` has a matching row and a `*.TOOL.md` file.

### Phase C — Naming and folder hygiene

**Skills**

- Folder name = **stable id** (kebab-case recommended for new skills: `my-skill-name`).
- Existing mixed styles (`kt_buddy`, `aws_check_...`) stay unless a **bulk rename** is approved (renames break deep links and `@` paths).

**Plans / todo / scratch**

- `plans/`: dated or ticket-prefixed names (`YYYY-MM-DD-...` or `JIRA-xxx-...`).
- `todo/`: optional stubs; prefer not to commit empty placeholders.
- `scratch/`: gitignored local only if introduced; never required for CI.

**Commands (Cursor slash commands)**

- `commands/` is reserved for **Cursor custom commands** JSON/markdown if the team adopts them; document format in README when first command lands.

### Phase D — Discoverability at repo root (optional)

- [ ] Add **`AGENTS.md`** at repository root (Cursor convention) with 15–25 lines: “For MIDAS agent work, see `.cursor/README.md` and `.cursor/JET.md`.” Reduces onboarding friction for agents that auto-read `AGENTS.md`.

### Phase E — Verification

- [ ] After moves/renames: grep for broken references to old paths in `docs/`, `.cursor/`, and `README` files.
- [ ] Confirm `docs/README.md` §2.4 still links to `.cursor/README.md`.

---

## 4. Consistency and best practices (gold standard)

### 4.1 When to add what

| Need | Add |
|------|-----|
| New **policy** or coding standard for the AI | `rules/<topic>.mdc` + narrow `globs` if not global |
| New **multi-step workflow** for the AI | `skills/<id>/SKILL.md` with YAML front-matter (`name`, `description`) |
| New **script the skill runs** | `scripts/` or `tools/` (tools if registry + TOOL.md pattern applies) |
| New **AWS/VPC constant** | Update `rules/solution_const.mdc` only after architecture owners approve |

### 4.2 Skill authoring checklist

- Front-matter `description` lists **triggers** and **boundaries** (“use when…”, “do not use when…”).
- “When to apply” near the top.
- Explicit **safety** / consent steps for mutations (Jenkins, AWS writes).
- Link to **scripts** with relative paths from repo root.

### 4.3 Tool authoring checklist

- Follow `tools/readme.md` gold-standard **TOOL.md** sections.
- Script + descriptor **stem alignment** as documented in the registry.

### 4.4 JET maintenance

- **JET.md** stays **short**: only coarse routes and extension rules.
- Detailed NL → command tables remain in **domain skills** (example: `skills/jenkins/SKILL.md`).

---

## 5. README work (newcomers)

Update `.cursor/README.md` to include:

1. **“New to MIDAS Cursor tooling?”** — 5-step path: read architecture + Jenkins rules → skim JET → pick a skill → run scripts with `--help` → never mutate shared AWS from laptop.
2. **“JET keyword”** — pointer to `.cursor/JET.md` and 2–3 examples.
3. **“Where to add a new capability”** — table mirroring §4.1 above.
4. **Link** to this plan file for restructuring tasks.

---

## 6. Out of scope

- Changing Jenkins job names, Terraform, or Helm in `deploy/` as part of this plan.
- Replacing skills with a custom CLI; JET remains documentation-first.

---

## 7. Success criteria

- A new developer can read **`.cursor/README.md` + `JET.md`** and know how to phrase requests and where to add a skill.
- No contradictory guidance between JET, jenkins skill, and `rules/jenkins.mdc` / `rules/tool.mdc` on **pipeline-first** and **CLI usage**.

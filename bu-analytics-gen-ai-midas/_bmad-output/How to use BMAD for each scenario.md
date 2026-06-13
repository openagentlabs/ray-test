# How to use BMAD for each scenario

This guide explains how to run **BMad 6.8.0** on the MIDAS (`EXLDecision.AI`) repository for four common workflows. BMad skills are Cursor agent skills under `.agents/skills/`; outputs go to `_bmad-output/`.

## Before you start

1. **Read** [_bmad-output/project-context.md](project-context.md) — agents must follow it (includes scenario routing and large-data rules).
2. **Put business files** in [_bmad-output/intake/](intake/README.md) under the correct subfolder.
3. **Use a fresh chat** for each BMad skill — do not chain spec + dev + review in one thread.
4. **Scenarios 1–3:** work is **not done** until tests are written, run, and **passing** — see [testing/scenario-test-gate.md](testing/scenario-test-gate.md).
5. **Readiness:** [bmad-readiness.md](bmad-readiness.md) lists what is prepped vs created per feature.
6. **Ask for help:** see [bmad-help prompt](#bmad-help-prompt) below.

### Feature slug (keep consistent across phases)

When two or more features run in parallel, each gets its own folder under `_bmad-output/planning-artifacts/<slug>/`, `_bmad-output/specs/spec-<slug>/`, and `_bmad-output/planning-artifacts/epics/<slug>/`.

**Convention:** Use the Jira ticket ID or a short kebab-case feature name as the slug. Pick it when you create the intake file and use it **unchanged** from PRD through SPEC, epics, and stories. Examples: `woe-export`, `MIDAS-42`, `segment-comparison`.

Full path table: [_bmad-output/intake/README.md](intake/README.md#feature-slug-required-for-parallel-features).

### Config locations

| File | Purpose |
|---|---|
| `_bmad/config.toml` | Project name, output folder |
| `_bmad/config.user.toml` | User name, skill level |
| `_bmad/bmm/config.yaml` | Planning / implementation artifact paths |

### Reference docs (this setup)

| Doc | Purpose |
|---|---|
| [bmad-workflow-map.md](bmad-workflow-map.md) | Phases and completion signals |
| [scenario-skill-matrix.md](scenario-skill-matrix.md) | Table: scenario → skills |
| [bmad-skill-catalog.md](bmad-skill-catalog.md) | Installed skills (CSV missing) |
| [spec-kernel.md](spec-kernel.md) | When to use `bmad-spec` |
| [scenarios/01-model-lab-feature.md](scenarios/01-model-lab-feature.md) | Scenario 1 detail |
| [scenarios/01-requirements-traceability.md](scenarios/01-requirements-traceability.md) | **PRD adherence, epics, REQ/CAP/ST IDs** |
| [scenarios/02-new-platform-module.md](scenarios/02-new-platform-module.md) | Scenario 2 detail |
| [scenarios/03-bug-resolution.md](scenarios/03-bug-resolution.md) | Scenario 3 detail |
| [scenarios/04-eks-scalability.md](scenarios/04-eks-scalability.md) | Scenario 4 detail |
| [testing/scenario-test-gate.md](testing/scenario-test-gate.md) | **Mandatory tests (scenarios 1–3)** |
| [testing/sme-verification-gate.md](testing/sme-verification-gate.md) | **SME sign-off for formulas / ML logic** |
| [bmad-readiness.md](bmad-readiness.md) | Setup complete vs per-feature artifacts |

---

## Mandatory test gate (scenarios 1–3)

| Step | What happens |
|---|---|
| Story | `bmad-create-story` includes **Test acceptance criteria** (paths + commands) |
| Implement | `bmad-dev-story` / `bmad-quick-dev` writes tests, runs them, reports green |
| **SME gate** | If tests cover **formulas / ML / metrics** → human shares package with **SME** → **sign-off required** before done |
| Optional QA | `bmad-qa-generate-e2e-tests` adds API/E2E depth (may also trigger SME gate) |
| Review | `bmad-code-review` blocks merge if tests missing, failing, or **SME not approved** |

**Run locally:**

```bash
bash _bmad-output/testing/run-scenario-tests.sh
```

Agents must paste pass/fail output before claiming completion.

### SME verification gate (formulas & data science)

**When:** Tests or features assert **business formulas**, **model training**, **evaluation metrics**, or **feature-engineering logic** (common in Model Lab and formula bugs).

**Full policy:** [testing/sme-verification-gate.md](testing/sme-verification-gate.md)

| Step | Who | Action |
|---|---|---|
| 1 | Agent | Tests green → create `_bmad-output/test-artifacts/sme-reviews/<slug>/ST-NNN/sme-review-package.md` |
| 2 | Agent | **Stop** — ask you to send the package to the SME |
| 3 | **You (developer)** | Share package + test files/fixtures with SME |
| 4 | **SME** | Confirms logic matches PRD or requests changes |
| 5 | **You** | Record outcome in `sme-signoff.md` (`Verdict: approved` or `changes requested`) |
| 6 | If **changes requested** | Fix feature/tests → re-run pytest/Vitest → update package → SME re-review |
| 7 | If **approved** | Proceed to `bmad-code-review` — development for that story is done |

**Agents must not** mark a story complete without SME **approved** when this gate applies.

Templates:

- `test-artifacts/templates/sme-review-package-template.md`
- `test-artifacts/templates/sme-signoff-template.md`

---

## How to invoke a skill

In Cursor Agent chat, use natural language that matches the skill description:

```
Use bmad-spec. ...
```

```
Use bmad-dev-story. Implement story _bmad-output/implementation-artifacts/...
```

**Multi-action skills:** `bmad-prd` supports create / update / validate intents in one skill. `bmad-agent-tech-writer` has actions with menu codes **WD**, **VD**, **EC**, **MG** (see skill folder).

**Menu codes:** Only **WB** (Working Backwards / `bmad-prfaq`) is recorded in-repo today. Other skills use names, not codes — see [bmad-skill-catalog.md](bmad-skill-catalog.md).

**Args / shortcuts:** Prefer file paths in the prompt (`intake/...`, `specs/spec-foo/SPEC.md`) rather than pasting large documents.

### Prompt writing tips

- Replace `<slug>`, `<ticket-id>`, `ST-NNN` with your real identifiers.
- Always cite `_bmad-output/project-context.md` and the scenario traceability doc when relevant.
- End every implement/review prompt with **done criteria** so the agent knows when to stop.
- One skill = one fresh chat.

### bmad-help prompt

```
Use bmad-help.

I am working on scenario <1|2|3|4> for MIDAS.
Feature/slug: <slug-or-ticket-id>
Completed so far: <e.g. PRD done, backlog approved, ST-002 in dev>
Artifacts I have: <list paths under _bmad-output/ if any>

What is the next required skill, what files should exist before I run it,
and give me a copy-paste prompt for that step.
```

---

## Scenario 1 — Model Lab feature

**Goal:** Build or improve features in Model Lab (`/models`, stepper UI, backend APIs).

**PRD adherence:** Uploaded PRD/requirements are **strictly** followed. See [scenarios/01-requirements-traceability.md](scenarios/01-requirements-traceability.md).

### Intake

Copy requirements to `_bmad-output/intake/01-model-lab/`.

### Skill order — **new feature** (required)

| Phase | Skill | Primary output |
|---|---|---|
| A | `bmad-prd` _(if intake is not already a numbered PRD)_ | `planning-artifacts/<slug>/prd.md` |
| B | `bmad-spec` | `specs/spec-<slug>/SPEC.md` + `traceability.md` |
| C | `bmad-create-epics-and-stories` | `planning-artifacts/epics/<slug>/backlog.md` + `traceability-matrix.md` |
| — | **Human gate** | Reply **approved** on backlog + matrix |
| **C★** | **`bmad-party-mode`** | **`party-reviews/backlog-roundtable.md`** — PRD + EKS validation |
| D | `bmad-create-story` | `implementation-artifacts/<slug>/story-ST-NNN.md` (one per story) |
| E | `bmad-ux` _(if UI)_ | `planning-artifacts/<slug>/ux-*.md` |
| **D★** | **`bmad-party-mode`** | **`party-reviews/pre-dev-ST-NNN.md`** — per story before code |
| F | `bmad-dev-story` | Code + tests (one `ST-*` per chat) |
| **F-SME** | **Human + SME** | SME reviews formula/ML tests — **sign-off required** |
| **F★** | **`bmad-party-mode`** _(recommended)_ | `party-reviews/pre-merge-ST-NNN.md` |
| G | `bmad-code-review` | Review + SME sign-off check |
| H | `jenkins_run` | Deploy after merge |
| Optional | `bmad-qa-generate-e2e-tests` | `_bmad-output/test-artifacts/` |

**Do not** use `bmad-quick-dev` for new multi-requirement features.

#### Phase A — `bmad-prd` (skip if intake is already a complete PRD)

```
Use bmad-prd. Intent: create.

Project: EXLDecision.AI (MIDAS Model Lab).
Slug: <slug>
Primary input (read by path, do not ask me to paste):
  - _bmad-output/intake/01-model-lab/<your-requirements>.md
  - _bmad-output/project-context.md
  - _bmad-output/scenarios/01-requirements-traceability.md

Deliverable:
  - _bmad-output/planning-artifacts/<slug>/prd.md

Requirements for the PRD:
  - Number every requirement REQ-001, REQ-002, … with no gaps.
  - Each REQ must cite intake file + section (e.g. intake/foo.md §3.2).
  - Include in-scope / out-of-scope, user flows, business rules (exact logic from intake — do not paraphrase formulas).
  - Include a Test strategy section: which backend routes and frontend components need pytest/Vitest.
  - Flag open questions as OQ-NNN instead of inventing behavior.

Done when: I can trace every sentence in intake to a REQ-* ID.
```

#### Phase B — `bmad-spec`

```
Use bmad-spec.

Slug: <slug>  (same folder: _bmad-output/specs/spec-<slug>/)
Inputs (read all by path):
  - _bmad-output/planning-artifacts/<slug>/prd.md  (or intake if PRD skipped)
  - _bmad-output/intake/01-model-lab/
  - _bmad-output/project-context.md
  - _bmad-output/scenarios/01-requirements-traceability.md

Deliverables:
  - SPEC.md with CAP-001, CAP-002, … (testable capabilities)
  - traceability.md: table REQ-* → CAP-* → intake reference
  - .decision-log.md updated

Rules:
  - Every REQ from the PRD must map to at least one CAP; no CAP without REQ parent.
  - Non-goals must forbid ai_gateway/ edits and whole-file CSV in memory.
  - Constraints must mention Cognito, apiInterceptor, PII/financial rules from project-context.
  - Do not add capabilities not supported by intake/PRD.

Done when: traceability.md has 100% REQ coverage and SPEC Success signal is measurable.
```

#### Phase C — `bmad-create-epics-and-stories`

```
Use bmad-create-epics-and-stories.

Feature slug: <slug>
Inputs (read by path):
  - _bmad-output/specs/spec-<slug>/SPEC.md
  - _bmad-output/specs/spec-<slug>/traceability.md
  - _bmad-output/planning-artifacts/<slug>/prd.md
  - _bmad-output/intake/01-model-lab/
  - _bmad-output/planning-artifacts/templates/epic-backlog-template.md
  - _bmad-output/planning-artifacts/templates/traceability-matrix-template.md
  - _bmad-output/scenarios/01-requirements-traceability.md

Outputs (create under):
  - _bmad-output/planning-artifacts/epics/<slug>/backlog.md
  - _bmad-output/planning-artifacts/epics/<slug>/traceability-matrix.md

Backlog rules:
  - EPIC-001, EPIC-002, … grouped by user value.
  - ST-001, ST-002, … sized for one bmad-dev-story session each (typically 1–3 days).
  - Each story: 3–8 SUB-* subtasks with concrete paths (e.g. backend/app/api/foo_routes.py).
  - Implementation order section: dependencies first (schemas → API → services → UI).
  - Every REQ-* appears in at least one ST-*; matrix columns: REQ, CAP, ST, SUB, tests, status=pending.

Do NOT write application code. Stop and ask me to review the backlog for approval.
```

#### Human gate (you, not a skill)

Review `backlog.md` and `traceability-matrix.md`. In the **next** chat, reply:

```
Backlog for <slug> is approved. Run party-mode backlog roundtable (Phase C★).
```

#### Phase C★ — `bmad-party-mode` (backlog — PRD + EKS) — **required**

Multi-agent roundtable **before** any `bmad-create-story` or `bmad-dev-story`. Ensures the backlog matches the PRD and is deployable on MIDAS EKS.

```
Use bmad-party-mode.

Topic: Model Lab feature <slug> — backlog review before development
Gate: backlog (Phase C★)

Required agents (spawn as independent subagents):
  - John (PM) — PRD / REQ-* coverage, no scope drift
  - Winston (architect) — EKS deployability, Helm, memory, S3/Redis, stateless pods
  - Amelia (dev) — story sizing, SUB-* feasibility, pytest/Vitest plan
  - Sally (UX) — only if backlog includes UI/stepper work

Read by path (pass to every agent):
  - _bmad-output/planning-artifacts/<slug>/prd.md
  - _bmad-output/specs/spec-<slug>/SPEC.md
  - _bmad-output/specs/spec-<slug>/traceability.md
  - _bmad-output/planning-artifacts/epics/<slug>/backlog.md
  - _bmad-output/planning-artifacts/epics/<slug>/traceability-matrix.md
  - _bmad-output/intake/01-model-lab/
  - _bmad-output/project-context.md
  - deploy/ecs-app/helm/midas-api-backend-svc/ (values, resources, replicas)
  - .cursor/rules/architecture.mdc

Discussion questions:
  1. Does every REQ-* in the PRD map to at least one ST-*? Any PRD logic missing from the backlog?
  2. Will any story violate PRD business rules if implemented as written?
  3. EKS: memory per pod/worker if this feature handles large CSV or caches?
  4. EKS: cross-pod state — only S3/Redis/Postgres, no sticky in-memory job state?
  5. Helm/Jenkins: do we need chart or pipeline changes? ADR triggers?
  6. What must change in backlog before dev starts?

After the roundtable, YOU (orchestrator) write synthesis using:
  - _bmad-output/planning-artifacts/templates/party-review-synthesis-template.md
Save to:
  - _bmad-output/planning-artifacts/epics/<slug>/party-reviews/backlog-roundtable.md

Done when: synthesis has Proceed = yes or yes-with-conditions, and I confirm conditions are resolved.
Do not start bmad-create-story until Proceed = yes.
```

#### Phase D — `bmad-create-story` (repeat per ST-* in a fresh chat)

```
Use bmad-create-story.

Create exactly one story file:
  - _bmad-output/implementation-artifacts/<slug>/story-ST-001.md

Inputs:
  - _bmad-output/planning-artifacts/epics/<slug>/backlog.md  (copy SUB-* for ST-001 only)
  - _bmad-output/specs/spec-<slug>/SPEC.md
  - _bmad-output/specs/spec-<slug>/traceability.md
  - _bmad-output/implementation-artifacts/templates/story-template.md
  - _bmad-output/project-context.md

Story file must include:
  - Traceability table (REQ-*, CAP-*, PRD §, intake §)
  - PRD adherence notes (business rules quoted or referenced)
  - Subtasks table SUB-* with checkboxes
  - Acceptance criteria mapped to CAP/REQ
  - Test acceptance criteria with exact pytest/Vitest paths and commands
  - ## SME verification required (yes/no) — if yes, list REQ formulas for SME and package path under test-artifacts/sme-reviews/<slug>/ST-NNN/

Do not create ST-002 or other stories in this chat.
Incorporate any open conditions from party-reviews/backlog-roundtable.md into this story if ST-001 is affected.
```

#### Phase D★ — `bmad-party-mode` (pre-dev per story) — **required before `bmad-dev-story`**

Run in a **fresh chat** after `story-ST-NNN.md` exists (and UX doc if UI story).

```
Use bmad-party-mode.

Topic: Model Lab <slug> — pre-implementation review for ST-NNN
Gate: pre-dev-ST-NNN (Phase D★)

Agents:
  - John (PM) + Mary (analyst) if REQ wording is ambiguous
  - Winston (architect) — EKS/memory/async/S3 path for this story only
  - Amelia (dev) — validate SUB-* order and files; confirm test plan

Read:
  - _bmad-output/implementation-artifacts/<slug>/story-ST-NNN.md
  - _bmad-output/planning-artifacts/epics/<slug>/party-reviews/backlog-roundtable.md
  - _bmad-output/specs/spec-<slug>/SPEC.md + traceability.md
  - _bmad-output/planning-artifacts/<slug>/prd.md (sections for this ST's REQ-*)
  - Relevant existing code paths listed in SUB-*
  - _bmad-output/project-context.md

Questions:
  1. Will implementation of this story exactly satisfy PRD logic for its REQ-*?
  2. Any SUB-* that would break EKS constraints (in-memory CSV, unbounded cache)?
  3. Changes needed to story file before Amelia codes?

Save synthesis to:
  - _bmad-output/planning-artifacts/epics/<slug>/party-reviews/pre-dev-ST-NNN.md

If conditions: update story-ST-NNN.md first, then run bmad-dev-story in a NEW chat.
```

#### Phase E — `bmad-ux` (optional, before dev for that story)

```
Use bmad-ux.

Feature: <slug> / story ST-001
Inputs:
  - _bmad-output/specs/spec-<slug>/SPEC.md
  - _bmad-output/implementation-artifacts/<slug>/story-ST-001.md
  - _bmad-output/intake/01-model-lab/  (wireframes if any)
  - Existing UI: frontend/src/components/steps/, frontend/src/pages/ModelBuilder.tsx

Deliverable:
  - _bmad-output/planning-artifacts/<slug>/ux-ST-001.md

Include: user flow, screen states (loading/empty/error), component paths, copy, validation.
Map each UX element to REQ-* and CAP-*. If UX requires a scope change, list spec updates needed — do not implement code.
```

#### Phase F — `bmad-dev-story` (one ST per chat)

**Prerequisite:** `party-reviews/pre-dev-ST-NNN.md` with Proceed = yes.

```
Use bmad-dev-story.

Implement ONLY this story (read full file):
  - _bmad-output/implementation-artifacts/<slug>/story-ST-001.md

Also read before coding:
  - _bmad-output/planning-artifacts/epics/<slug>/party-reviews/pre-dev-ST-001.md
  - _bmad-output/planning-artifacts/epics/<slug>/party-reviews/backlog-roundtable.md
  - _bmad-output/intake/01-model-lab/
  - _bmad-output/planning-artifacts/<slug>/prd.md
  - _bmad-output/specs/spec-<slug>/SPEC.md
  - _bmad-output/specs/spec-<slug>/traceability.md
  - _bmad-output/project-context.md
  - _bmad-output/testing/scenario-test-gate.md
  - _bmad-output/scenarios/01-requirements-traceability.md

Implementation rules:
  - Complete every SUB-* in order; check off in the story file when done.
  - Business logic must match PRD/intake exactly — if impossible, STOP and report; do not improvise.
  - New backend routes in backend/app/api/*_routes.py; no appends to llm_service.py or monolithic routes.py.
  - Do not edit ai_gateway/**.

Testing (mandatory before you finish):
  - Write/update tests listed in the story Test acceptance criteria.
  - Run: cd backend && python3 -m pytest -q <paths>
  - Run: cd frontend && npm run test  (or npx vitest run <paths>)
  - Paste pass counts in your final summary.

Done when: all SUB-* complete, all AC satisfied, tests green, no out-of-scope files changed.
Honor all conditions from party pre-dev synthesis (EKS-safe patterns only).

If this story includes formulas, ML training, or evaluation metrics (see story ## SME verification required):
  - Create SME package at _bmad-output/test-artifacts/sme-reviews/<slug>/ST-001/
  - Use templates under test-artifacts/templates/sme-review-package-template.md
  - Do NOT claim development complete — instruct me to share the package with our SME and wait for sign-off.
```

#### Phase F-SME — Human + SME sign-off (when formulas / ML logic apply)

**After** tests are green and the agent created `sme-review-package.md`.

**You (developer):**

1. Send to SME:
   - `_bmad-output/test-artifacts/sme-reviews/<slug>/ST-NNN/sme-review-package.md`
   - Linked test files (e.g. `backend/tests/test_....py`)
   - Fixture notes / small sample data if referenced
   - PRD sections for the formulas under review (`REQ-*`)
2. Ask SME: *Do the implementation and tests correctly reflect the PRD formulas and data-science logic?*
3. Record response in `sme-signoff.md` (copy from `sme-signoff-template.md`).

**If SME approves** — reply in a **new** chat:

```
SME sign-off approved for <slug> ST-NNN.
sme-signoff.md is at _bmad-output/test-artifacts/sme-reviews/<slug>/ST-NNN/sme-signoff.md
Proceed to bmad-code-review (or party-mode pre-merge if using).
```

**If SME requests changes** — reply in a **new** chat:

```
Use bmad-dev-story.

SME requested changes for <slug> ST-NNN.
Feedback: <paste SME comments>
sme-signoff path: _bmad-output/test-artifacts/sme-reviews/<slug>/ST-NNN/
Update implementation and tests per SME; re-run pytest/Vitest; refresh sme-review-package.md.
Stop again for SME re-review after tests green.
```

Development for this story is **not done** until `sme-signoff.md` shows **Verdict: approved**.

#### Phase F★ — `bmad-party-mode` (pre-merge, optional but recommended)

```
Use bmad-party-mode.

Topic: <slug> ST-NNN — post-implementation check before code review
Gate: pre-merge

Agents: Winston (architect), John (PM), Amelia (dev)

Read: story file, git diff vs main, test output summary, party-reviews/pre-dev-ST-NNN.md

Confirm:
  - Implemented code matches PRD for this story's REQ-*
  - No EKS anti-patterns introduced (whole-file load, global cache, blocking sync on event loop)
  - Helm/resource impact documented if any

Save: _bmad-output/planning-artifacts/epics/<slug>/party-reviews/pre-merge-ST-NNN.md
Then run bmad-code-review in a new chat.
```

#### Phase G — `bmad-code-review`

```
Use bmad-code-review.

Scope: Model Lab feature <slug>, story ST-001 (branch or diff vs main).
Read:
  - _bmad-output/implementation-artifacts/<slug>/story-ST-001.md
  - _bmad-output/planning-artifacts/epics/<slug>/traceability-matrix.md
  - _bmad-output/planning-artifacts/epics/<slug>/party-reviews/pre-dev-ST-001.md
  - _bmad-output/planning-artifacts/epics/<slug>/party-reviews/pre-merge-ST-001.md (if exists)
  - _bmad-output/test-artifacts/sme-reviews/<slug>/ST-001/sme-signoff.md (if SME gate applies)
  - _bmad-output/specs/spec-<slug>/traceability.md
  - _bmad-output/project-context.md

Review checklist:
  0. SME: if formula/ML tests exist, sme-signoff.md must show Verdict=approved — else FAIL.
  1. Traceability: every REQ/CAP for this story has code + test mapping; flag orphans.
  2. PRD adherence: no undeclared business logic; formulas match PRD.
  3. Security: auth on new routes, 401 tests, no PII in logs.
  4. Tests: pytest/Vitest exist and would pass; loading/empty/error for UI.
  5. Hygiene: no ai_gateway edits; file-size discipline.

Output: findings by severity (blocker/major/minor) + explicit pass/fail for traceability audit.
```

#### Optional — `bmad-qa-generate-e2e-tests`

```
Use bmad-qa-generate-e2e-tests.

Feature: <slug>, story ST-001 (already implemented).
Inputs:
  - _bmad-output/implementation-artifacts/<slug>/story-ST-001.md
  - Current code under backend/ and frontend/ for this story
  - _bmad-output/testing/scenario-test-gate.md

Generate additional API or E2E tests complementing existing pytest/Vitest.
Output under _bmad-output/test-artifacts/. Do not change production code unless a test reveals a real bug — then file as blocker.
```

#### Phase H — Jenkins (after PR merge)

```
Use jenkins_run.

Deploy the merged PR for <slug> to dev.
Confirm ENVIRONMENT=dev with me before trigger.
Watch until terminal state; auto-approve input steps per skill rules.
Report traffic-light summary when finished.
```

---

### Skill order — **small improvement**

| Step | Skill |
|---|---|
| 1 | `bmad-create-story` |
| 2 | `bmad-dev-story` |
| 3 | `bmad-code-review` |

#### Small improvement — `bmad-create-story`

```
Use bmad-create-story.

Slug: <slug>
Scope: small improvement — single story ST-001 only.
Input:
  - _bmad-output/intake/01-model-lab/<file>.md  (cite REQ-* affected)
  - _bmad-output/specs/spec-<slug>/  (if exists; else create minimal traceability note in story)

Output: _bmad-output/implementation-artifacts/<slug>/story-ST-001.md
Include SUB-* (2–5 items), Test acceptance criteria, PRD adherence notes.
```

#### Small improvement — `bmad-dev-story`

```
Use bmad-dev-story.

Story: _bmad-output/implementation-artifacts/<slug>/story-ST-001.md
Follow PRD/intake for the cited REQ-* only. Minimal diff.
Run tests per _bmad-output/testing/scenario-test-gate.md and paste results.
Done when: SUB-* complete and tests green.
If formula/ML logic: create SME package and wait for human SME sign-off before claiming done.
```

#### Small improvement — `bmad-code-review`

```
Use bmad-code-review.

Small improvement for <slug> ST-001. Verify REQ-* satisfied, regression tests pass, no scope creep.
```

### When to use which role

| Need | Skill |
|---|---|
| Unclear requirements | `bmad-agent-analyst` or `bmad-prd` |
| UI flow | `bmad-ux` or `bmad-agent-ux-designer` |
| Implementation | `bmad-dev-story` / `bmad-agent-dev` |
| Pre-merge demo | `bmad-checkpoint-preview` |

#### Optional — `bmad-agent-analyst` (vague intake)

```
Use bmad-agent-analyst.

I need clarity before PRD/spec for Model Lab feature <slug>.
Read: _bmad-output/intake/01-model-lab/ and _bmad-output/project-context.md.
Output: structured questions, missing REQ candidates, and recommended next skill (bmad-prd vs bmad-spec).
Do not implement code.
```

#### Optional — `bmad-checkpoint-preview` (pre-merge)

```
Use bmad-checkpoint-preview.

Walk me through the change for <slug> ST-001: what changed, what to test manually in Model Lab,
risks, and demo script. Read story file and diff vs main.
```

### Escalation

| Issue | Action |
|---|---|
| Spec wrong | Re-run `bmad-spec` same `spec-<slug>/` folder; update traceability.md |
| Backlog wrong | Re-run `bmad-create-epics-and-stories`; re-approve |
| Scope creep | `bmad-correct-course` with intake + SPEC links |

---

## Scenario 2 — New platform module

**Goal:** New module on the platform with **login/logout only** from MIDAS.

### Intake

`_bmad-output/intake/02-platform-module/`

### Skill order

| Step | Skill | Primary output |
|---|---|---|
| 1 | `bmad-create-architecture` | `planning-artifacts/<module>/architecture-*.md` |
| 2 | `bmad-spec` | `specs/spec-module-<name>/` |
| 3 | `bmad-prd` _(optional)_ | `planning-artifacts/<module>/prd.md` |
| 4 | `bmad-create-story` | `implementation-artifacts/<module>/story-*.md` |
| 5 | `bmad-dev-story` | Module code + tests |
| 6 | `bmad-code-review` | Boundary + security review |

#### Step 1 — `bmad-create-architecture`

```
Use bmad-create-architecture.

New platform module: <module-name> (slug: module-<name>)
Inputs:
  - _bmad-output/intake/02-platform-module/
  - _bmad-output/project-context.md
  - .cursor/rules/architecture.mdc (private VPC, EKS, no public endpoints)

Hard boundary:
  - ONLY integration with MIDAS: Cognito login/logout (reuse AuthCallback / authService patterns).
  - FORBIDDEN: imports from Model Lab, ModelBuilder, dataset managers, training services, ai_gateway/**.

Deliverable under _bmad-output/planning-artifacts/module-<name>/:
  - architecture document: deployment unit (new Helm chart vs service), data stores, network, secrets
  - auth-only boundary diagram
  - ADR triggers if new AWS service or data store
  - pod/worker memory notes if module handles files

Done when: a developer could implement without touching Model Lab code paths.
```

#### Step 2 — `bmad-spec`

```
Use bmad-spec.

Slug: module-<name>
Inputs:
  - _bmad-output/planning-artifacts/module-<name>/architecture*.md
  - _bmad-output/intake/02-platform-module/
  - _bmad-output/project-context.md

Non-goals (must be explicit):
  - No imports from backend/app/services except documented auth/session helpers
  - No Model Lab UI or APIs
  - No ai_gateway edits

Deliverables: specs/spec-module-<name>/SPEC.md + companions + traceability to intake REQ-* if present.
```

#### Step 3 — `bmad-prd` (optional, multi-release modules)

```
Use bmad-prd. Intent: create.

Module: module-<name>
Inputs: specs/spec-module-<name>/SPEC.md, intake/02-platform-module/, architecture doc.
Output: _bmad-output/planning-artifacts/module-<name>/prd.md with REQ-* IDs and release phases.
```

#### Step 4 — `bmad-create-story` (first vertical slice)

```
Use bmad-create-story.

Module: module-<name>
Create story ST-001 — thinnest end-to-end slice (scaffold + Cognito callback + health route).
Use implementation-artifacts/templates/story-template.md.
Include Test acceptance criteria: auth smoke (login, logout, 401) and module-specific tests.
Output: _bmad-output/implementation-artifacts/module-<name>/story-ST-001.md
```

#### Step 5 — `bmad-dev-story`

```
Use bmad-dev-story.

Story: _bmad-output/implementation-artifacts/module-<name>/story-ST-001.md
Read architecture + SPEC + project-context + scenario-test-gate.md.

Rules:
  - New package/chart path only; document every shared auth file touched.
  - Prove no imports from Model Lab (list import graph in summary).
  - Tests: pytest/Vitest + 401 on protected routes; run and paste green output.

Done when: ST-001 AC met, tests green, boundary checklist satisfied.
```

#### Step 6 — `bmad-code-review`

```
Use bmad-code-review.

Module: module-<name>, story ST-001.
Verify:
  - Import graph: no Model Lab / training / ai_gateway
  - Auth-only MIDAS coupling
  - organisation_id / tenancy if module stores data
  - Tests pass; security checklist from project-context
Fail if undeclared AWS surface or missing ADR.
```

### Escalation

```
Use bmad-party-mode.

Topic: architecture decision for module-<name> — <e.g. separate DB vs shared Postgres schema>.
Participants: bmad-agent-architect, bmad-agent-pm.
Read intake/02-platform-module/ and planning-artifacts/module-<name>/.
Output: recommendation + whether ADR required at docs/adr/.
```

New AWS service → draft ADR before `bmad-dev-story`.

---

## Scenario 3 — Bug resolution

**Goal:** Fix UI, formulas, security, or deployment issues.

### Intake

`_bmad-output/intake/03-bug-resolution/<ticket-id>/`

### Skill order

| Step | Skill | Primary output |
|---|---|---|
| 1 | `bmad-investigate` | Evidence-graded root cause |
| 2 | `bmad-quick-dev` or `bmad-dev-story` | Fix + regression test |
| 3 | `bmad-review-edge-case-hunter` _(optional)_ | Edge-case report |
| 4 | `bmad-code-review` | Review + security sign-off |

#### Step 1 — `bmad-investigate`

```
Use bmad-investigate.

Bug ID: <ticket-id>  (e.g. MIDAS-456)
Title: <one-line summary>
Class: <UI | backend-formula | security | deploy>  (your best guess)

Evidence folder (read all files):
  - _bmad-output/intake/03-bug-resolution/<ticket-id>/
  - Include: repro-steps.md, expected-vs-actual, screenshots, API HAR, logs (redacted)

Also read:
  - _bmad-output/project-context.md
  - _bmad-output/scenarios/03-bug-resolution.md
  - _bmad-output/testing/scenario-test-gate.md

Deliverable:
  - Ranked hypotheses with evidence strength (confirmed / likely / speculative)
  - Exact file paths and line areas to change
  - Recommended fix scope (minimal diff)
  - Regression test location: backend/tests/test_<what>.py or frontend/*.test.tsx

Do not implement the fix in this chat.
```

#### Step 2a — `bmad-quick-dev` (small, localized fix)

```
Use bmad-quick-dev.

Fix bug <ticket-id> per investigation findings:
  - _bmad-output/intake/03-bug-resolution/<ticket-id>/  (and your investigation summary from prior chat if needed)

Rules:
  - Minimal surgical diff only — no refactors, no drive-by changes.
  - Add regression test that fails on main and passes with fix.
  - Read _bmad-output/project-context.md (auth, PII, async FastAPI).
  - Do not edit ai_gateway/**.

Testing (mandatory):
  - Run scoped pytest or vitest; paste command + pass output.
  - For security bugs: include 401/403 test if applicable.

Done when: repro fixed, regression test green, summary lists files changed.

If fix involves formulas/metrics/training logic:
  - Create _bmad-output/test-artifacts/sme-reviews/bugs/<ticket-id>/sme-review-package.md
  - Ask human to obtain SME sign-off before marking complete.
```

#### Step 2b — `bmad-dev-story` (fix needs story/AC)

```
Use bmad-dev-story.

First create/use story: _bmad-output/implementation-artifacts/bugs/<ticket-id>/story-ST-001.md
Investigation: <paste path or summary>
Implement fix per story SUB-*; regression test named test_regression_<ticket-id> or similar.
Follow scenario-test-gate.md. Done when tests green.
```

#### Step 3 — `bmad-review-edge-case-hunter` (optional)

```
Use bmad-review-edge-case-hunter.

Review the fix for <ticket-id> on branch <name>.
Focus: state conflicts, apiInterceptor SessionExpiredError, formula boundary values, concurrent saves.
Read only the diff — report unhandled edge cases, not style nits.
```

#### Step 4 — `bmad-code-review`

```
Use bmad-code-review.

Bug fix <ticket-id>, class: <UI|backend|security|deploy>.
Verify:
  - Root cause addressed (not symptom-only)
  - Regression test covers repro
  - Tests pass; no PII in logs; auth intact
  - No unrelated files in diff
For security/financial routes: mandatory deep review — fail if regression test missing.
For backend-formula bugs: require sme-signoff.md approved when regression test encodes formula logic.
```

#### Scenario 3 — SME sign-off (formula / ML bugs)

After `bmad-quick-dev` or `bmad-dev-story` when the fix touches **calculations, metrics, or training**:

1. Agent produces `test-artifacts/sme-reviews/bugs/<ticket-id>/sme-review-package.md`
2. You share with SME (include regression test + PRD/intake formula excerpt)
3. Record `sme-signoff.md`
4. If changes requested → fix loop; if approved → `bmad-code-review`

```
Use bmad-dev-story.

Bug <ticket-id> — SME feedback iteration.
Prior package: _bmad-output/test-artifacts/sme-reviews/bugs/<ticket-id>/
SME feedback: <paste>
Update code/tests; re-run pytest; refresh sme-review-package; stop for SME re-review.
```

### Deploy / infra bugs (operational, not BMad)

#### `tf_validate`

```
Use tf_validate.

Scan Terraform under deploy/ for Checkov violations related to <ticket-id>.
For each finding: explain root cause, propose fix, ask Y/N before applying.
Re-run until clean or document accepted exceptions.
```

#### `jenkins_run`

```
Use jenkins_run.

Bug <ticket-id> was a deploy/pipeline issue. Deploy current branch to dev.
Confirm ENVIRONMENT=dev before trigger. Watch until terminal; report failing stage logs if any.
```

### Escalation

| Symptom | Next |
|---|---|
| OOM / 5 GB CSV | Scenario 4 research + architecture |
| Auth / PII | Mandatory `bmad-code-review` |
| Can't reproduce | `bmad-party-mode` |

---

## Scenario 4 — EKS scalability

**Goal:** Support 5→20 users with 5→20 GB CSV paths on EKS without whole-file RAM.

### Intake

`_bmad-output/intake/04-eks-scalability/`

### Skill order

| Step | Skill | Primary output |
|---|---|---|
| 1 | `bmad-technical-research` | Options + tradeoffs doc |
| 2 | `bmad-create-architecture` | Scale architecture + memory math |
| 3 | `bmad-spec` | `specs/spec-<slug>/` |
| 4 | `bmad-create-story` | Implementation story |
| 5 | `bmad-dev-story` | Code + perf tests |
| 6 | `bmad-code-review` | Scale + memory review |

#### Step 1 — `bmad-technical-research`

```
Use bmad-technical-research.

Topic: MIDAS large CSV concurrency on EKS
Read:
  - _bmad-output/intake/04-eks-scalability/
  - _bmad-output/project-context.md (large-data section)
  - backend/app/api/chunked_upload.py, backend/app/services/background_jobs.py
  - deploy/ecs-app/helm/midas-api-backend-svc/ values

Targets:
  - Near-term: 5 concurrent users, 5 GB CSV per user path
  - Target: 20 users, 20 GB CSV
  - No whole-file RAM; S3 + Redis + Postgres roles

Output: _bmad-output/planning-artifacts/<slug>/research-eks-csv.md with options, risks, recommendation.
Cite pod memory × workers × replicas for each option.
```

#### Step 2 — `bmad-create-architecture`

```
Use bmad-create-architecture.

Initiative: <slug> (EKS CSV scale)
Inputs: research doc, intake/04-eks-scalability/, project-context, architecture.mdc.

Must include:
  - Data flow: upload → S3 → chunked processing → job status in Redis/S3
  - Table: per-request RAM, per-worker RAM, per-pod RAM at 5 and 20 users
  - HPA/replica strategy; bounded caches with TTL
  - Helm impact (replicaCount, webConcurrency, memory requests)

Output: _bmad-output/planning-artifacts/<slug>/architecture-eks-scale.md
ADR list if new AWS patterns.
```

#### Step 3 — `bmad-spec`

```
Use bmad-spec.

Slug: <slug>  (e.g. eks-csv-scale)
Inputs: architecture doc, intake, project-context large-data rules.

Constraints (non-negotiable in SPEC):
  - No full 5–20 GB CSV in process memory
  - Cross-pod state via S3/Redis only
  - Explicit eviction/TTL on any cache
  - Test + ops verification required for done

Deliverables: SPEC.md + companions; Success signal must be measurable (e.g. concurrent finalize test, memory ceiling).
```

#### Step 4 — `bmad-create-story`

```
Use bmad-create-story.

Spec: _bmad-output/specs/spec-<slug>/
Create ST-001 for first incremental scale improvement (e.g. concurrent chunked finalize + perf test).
Include Test AC: pytest perf ceiling, reference test_chunked_upload.py patterns.
Include ops verification checklist items from scenarios/04-eks-scalability.md.
```

#### Step 5 — `bmad-dev-story`

```
Use bmad-dev-story.

Story: _bmad-output/implementation-artifacts/<slug>/story-ST-001.md
Read SPEC, architecture, project-context, background_jobs.py, chunked_upload.py.

Rules:
  - Streaming/chunked only; document memory impact in PR summary.
  - Add/update tests proving no full-file load; run pytest with output pasted.
  - Complete ops verification notes: pod count, worker count, expected RAM.

Done when: tests green + ops checklist draft filled for this story.
```

#### Step 6 — `bmad-code-review`

```
Use bmad-code-review.

EKS scale change <slug> ST-001.
Require:
  - Evidence of chunked/streaming behavior
  - Perf/memory tests present
  - No unbounded global caches
  - Helm/resource implications called out
Fail if whole-file read introduced or cross-pod in-memory state added.
```

### Verification (required)

Follow [scenarios/04-eks-scalability.md](scenarios/04-eks-scalability.md) operational checklist. Do not mark done without tests and Helm/memory notes.

### Escalation

Needs HPA/custom metrics → architecture + ADR. Frontend loading full CSV → scenario 1 + API changes.

---

## Dev vs architect vs QA vs investigate

| Role | Skill | When |
|---|---|---|
| **Roundtable (PRD + EKS)** | **`bmad-party-mode`** | **Scenario 1:** after backlog approval + before each dev story; spawns PM, architect, dev, UX |
| **Investigate** | `bmad-investigate` | Unknown cause, production bugs, complex regressions |
| **Architect** | `bmad-create-architecture`, `bmad-agent-architect` | New module, scale design; also in party-mode for EKS |
| **Dev** | `bmad-dev-story`, `bmad-quick-dev`, `bmad-agent-dev` | After party pre-dev gate; one ST per chat |
| **QA** | `bmad-qa-generate-e2e-tests` | After dev, optional E2E/API depth; **does not replace** pytest/Vitest gate |
| **SME** | **Human + SME** | After green tests when formulas/ML/metrics are involved — **sign-off before review** |
| **Review** | `bmad-code-review`, `bmad-review-edge-case-hunter` | After SME approved (if applicable); mandatory for security/scale |

---

## Operational skills (MIDAS repo, not BMad)

Always confirm **dev/uat/prod** before deploy.

#### `git_pull_commit_push` (with commit approval)

```
Use git_pull_commit_push.

Pull latest, summarize my staged changes, propose commit message for <slug>/<ticket-id>.
Wait for my approval before commit and push.
```

#### `jp_pull_commit_push` (auto commit message, no Jenkins)

```
Use jp_pull_commit_push.

Pull, commit with generated message, push. Stop on merge conflict.
```

#### `jenkins_run`

```
Use jenkins_run.

Deploy branch <branch> to <dev|uat|prod> for <feature or ticket>.
Wait for build to start, watch until terminal, auto-approve pipeline inputs.
Deliver traffic-light summary and failure root cause if not SUCCESS.
```

---

## Gaps and manual steps

| Gap | What to do |
|---|---|
| `_bmad/_config/bmad-help.csv` missing | Use [bmad-skill-catalog.md](bmad-skill-catalog.md); re-run BMad installer for CSV |
| `planning-artifacts/` / `implementation-artifacts/` empty | Templates in `*/templates/`; real PRD/story on first skill run |
| Test deps not installed locally | `bash _bmad-output/testing/run-scenario-tests.sh` installs and runs |
| Large CSV in intake | Do not commit; use S3 dev bucket + path reference in markdown |
| Submodule `ai_gateway/` | Never edit; bump only via explicit submodule PR |

---

## Quick “which scenario am I?”

| You are… | Scenario |
|---|---|
| Changing Model Lab steps, training, evaluation UI | **1** |
| Building a new app area that only shares login | **2** |
| Fixing a defect or incident | **3** |
| Improving upload size, concurrency, pod memory, HPA | **4** |

When unsure, use the [bmad-help prompt](#bmad-help-prompt) at the top of this guide.

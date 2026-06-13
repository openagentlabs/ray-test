# Scenario 1 — Model Lab feature build or improve

## Scope

Features and improvements inside **Model Lab**: project selection, 9-step model-building pipeline (`ModelBuilder`), evaluation dashboards, and related backend APIs/services.

**In scope paths (typical):**

- `frontend/src/pages/ModelBuilder.tsx`, `frontend/src/components/steps/`
- `frontend/src/pages/ModelEvaluation*.tsx`, `frontend/src/services/*Service.ts`
- `backend/app/api/*_routes.py`, `backend/app/services/` (new files — do not append to `llm_service.py` or monolithic `routes.py`)
- `backend/app/models/schemas.py` for API contracts

**Out of scope:** New standalone platform modules (scenario 2), pure infra scale work without feature UX (scenario 4 only).

**Traceability policy:** [01-requirements-traceability.md](01-requirements-traceability.md) — PRD/intake logic is mandatory; dev is task-by-task per story.

---

## Preconditions

1. Business materials in `_bmad-output/intake/01-model-lab/` (PRD, requirements, wireframes — **source of truth**).
2. Agent reads `_bmad-output/project-context.md`.
3. For **new features**: complete phases A–D below and obtain **backlog approval** before any `bmad-dev-story`.

---

## Workflow — new feature (full chain)

### Phase A — PRD with numbered requirements

**When:** Intake is notes/brain dump, or PRD lacks `REQ-*` IDs.

| Step | Skill | Output |
|---|---|---|
| A1 | `bmad-prd` | `_bmad-output/planning-artifacts/<slug>/prd.md` with `REQ-001`, `REQ-002`, … |

**Prompt:**

```
Use bmad-prd. Create PRD from _bmad-output/intake/01-model-lab/<files>.
Slug: <slug>. Number every requirement REQ-NNN. Cite intake section per REQ.
Output: _bmad-output/planning-artifacts/<slug>/prd.md
```

**Skip A** if intake is already a complete numbered PRD — add `REQ-*` labels in place if missing.

---

### Phase B — SPEC + traceability companion

| Step | Skill | Output |
|---|---|---|
| B1 | `bmad-spec` | `specs/spec-<slug>/SPEC.md` (CAP-* IDs) |
| B2 | _(same run)_ | `specs/spec-<slug>/traceability.md` (REQ ↔ CAP ↔ intake) |

**Prompt:**

```
Use bmad-spec. Slug: <slug>.
Input: planning-artifacts/<slug>/prd.md (or intake), project-context.md, intake/01-model-lab/.
Create traceability.md mapping every REQ to CAP. No capabilities without REQ parent.
Follow _bmad-output/scenarios/01-requirements-traceability.md.
```

**Done when:** Every intake/PRD requirement has `REQ-*`; every `CAP-*` is testable and traced.

---

### Phase C — Epics, stories, subtasks (required before dev)

| Step | Skill | Output |
|---|---|---|
| C1 | `bmad-create-epics-and-stories` | `planning-artifacts/epics/<slug>/backlog.md` |
| C2 | _(same run)_ | `planning-artifacts/epics/<slug>/traceability-matrix.md` |

**Prompt:**

```
Use bmad-create-epics-and-stories.
Input: specs/spec-<slug>/, planning-artifacts/<slug>/prd.md, intake/01-model-lab/.
Output under planning-artifacts/epics/<slug>/.
Every REQ maps to ≥1 ST-*. Each story has 3–8 SUB-* with file paths. Order by dependency.
Do not implement code.
```

**Human gate:** Review backlog + matrix. Reply **approved** before Phase C★.

---

### Phase C★ — Multi-agent roundtable (`bmad-party-mode`) — **required after backlog approval**

Validates backlog against **PRD** and **EKS deployability** before any story files or code.

| Agents | Role in roundtable |
|---|---|
| **John** (`bmad-agent-pm`) | REQ coverage, no scope drift from PRD |
| **Winston** (`bmad-agent-architect`) | EKS, Helm, memory, S3/Redis, stateless pods |
| **Amelia** (`bmad-agent-dev`) | Story sizing, SUB-* feasibility, test strategy |
| **Sally** (`bmad-agent-ux-designer`) | _(if UI epics)_ Stepper/UI alignment with PRD |

**Output:** `_bmad-output/planning-artifacts/epics/<slug>/party-reviews/backlog-roundtable.md` (use synthesis template)

**Proceed to Phase D only if synthesis says proceed = yes or yes-with-conditions (conditions resolved).**

See [How to use BMAD for each scenario.md](../How%20to%20use%20BMAD%20for%20each%20scenario.md) for the full prompt.

---

### Phase D — One story file per ST-*

| Step | Skill | Output |
|---|---|---|
| D1 | `bmad-create-story` | `implementation-artifacts/<slug>/story-ST-001.md` (repeat per story) |

**Prompt (one ST per chat):**

```
Use bmad-create-story. Create story ST-001 only for spec specs/spec-<slug>/.
Copy SUB-* from planning-artifacts/epics/<slug>/backlog.md.
Include Traceability (REQ/CAP), Test acceptance criteria, PRD adherence notes.
```

Repeat for `ST-002`, `ST-003`, … in **separate fresh chats**.

---

### Phase D★ — Pre-dev roundtable (`bmad-party-mode`) — **required before each `bmad-dev-story`**

Per story, after `story-ST-NNN.md` exists (and UX doc if applicable).

| Agents | Focus |
|---|---|
| **John** / **Mary** | This ST satisfies REQ/CAP — no missing PRD logic |
| **Winston** | Implementation plan is EKS-safe (memory, async, shared stores) |
| **Amelia** | SUB-* order, files, tests — ready to implement |

**Output:** `_bmad-output/planning-artifacts/epics/<slug>/party-reviews/pre-dev-ST-NNN.md`

**Then** run `bmad-dev-story` in a **new** chat, referencing the synthesis (conditions must be folded into the story file first).

---

### Phase E — Implement task-by-task (one story per chat)

| Step | Skill | Rule |
|---|---|---|
| E1 | `bmad-dev-story` | **One `ST-*` per chat** — complete all `SUB-*` before closing |
| E2 | _(optional)_ | `bmad-ux` before E1 if UI not fully specified in Phase B/C |

**Prompt:**

```
Use bmad-dev-story. Implement ONLY implementation-artifacts/<slug>/story-ST-001.md.
Strictly follow intake, PRD, SPEC, and traceability.md. Complete every SUB-*.
Run tests per scenario-test-gate.md. If PRD logic cannot be implemented, stop and report — do not improvise.
```

**Not allowed for new features:** `bmad-quick-dev` spanning multiple requirements.

---

### Phase F — UX (if needed)

Run `bmad-ux` **before** Phase E when screens are new — output must align with `REQ-*` / `CAP-*` (update spec if UX changes scope).

---

### Phase F★ — Pre-merge roundtable (`bmad-party-mode`) — **recommended before `bmad-code-review`**

Optional for small stories; **recommended** when the story touches APIs, large data, or Helm values.

**Output:** `party-reviews/pre-merge-ST-NNN.md` — confirm PRD + EKS still satisfied after implementation.

---

### Phase G — Review and traceability update

| Step | Skill |
|---|---|
| G1 | `bmad-code-review` — includes PRD adherence + traceability audit |
| G2 | Human updates `traceability-matrix.md` Status → `done` for merged ST-* |

**Prompt:**

```
Use bmad-code-review for feature <slug> story ST-001.
Verify code matches PRD/SPEC, all REQ/CAP for this story are covered by tests, no undeclared logic.
```

---

### Phase H — Ship (operational)

PR merge → `jenkins_run` (confirm environment).

---

## Workflow — small improvement (light path)

For a **single** localized change tied to one `REQ` or `SUB`:

1. Ensure `REQ-*` exists in intake or spec traceability.
2. `bmad-create-story` → one story with subtasks.
3. `bmad-dev-story` → `bmad-code-review`.

Still require tests green and PRD citation in the story.

---

## Escalation

| Situation | Next skill |
|---|---|
| Requirements vague | `bmad-agent-analyst` before Phase A |
| PRD vs spec conflict | `bmad-spec` update + matrix fix |
| Scope change mid-sprint | `bmad-correct-course` |
| Pre-merge demo | `bmad-checkpoint-preview` |
| Large program | `bmad-check-implementation-readiness` before Phase A |

---

## Completion checklist (new feature)

- [ ] PRD/intake requirements all have `REQ-*`
- [ ] SPEC + `traceability.md` complete
- [ ] Epic backlog + matrix approved
- [ ] **Party backlog roundtable** (`party-reviews/backlog-roundtable.md`) — proceed = yes
- [ ] **Party pre-dev roundtable** per ST before `bmad-dev-story`
- [ ] Every `ST-*` implemented in its own dev chat; all `SUB-*` checked
- [ ] **Tests written, run, passing** ([scenario-test-gate.md](../testing/scenario-test-gate.md))
- [ ] **SME sign-off approved** if formulas/ML ([sme-verification-gate.md](../testing/sme-verification-gate.md))
- [ ] `bmad-code-review` traceability audit passed
- [ ] Matrix updated; no `REQ-*` left `pending` without documented deferral
- [ ] No `ai_gateway/` edits

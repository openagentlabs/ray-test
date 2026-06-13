# Scenario 1 — Requirements traceability and PRD adherence

**Applies to:** All **new** Model Lab features (improvements to existing flows may use a lighter path — see [01-model-lab-feature.md](01-model-lab-feature.md)).

## Policy

1. **Source of truth** — Developer/business documents in `_bmad-output/intake/01-model-lab/` and the derived **PRD** + **SPEC** are authoritative. Implementation must not add, omit, or reinterpret business logic without an explicit spec/PRD update.
2. **Traceability** — Every capability, story, subtask, and test maps to stable IDs (`REQ-*`, `CAP-*`, `ST-*`, `SUB-*`).
3. **No dev before backlog** — `bmad-dev-story` runs only against a **single approved story** that lists subtasks; epic backlog must exist first.
4. **Verify on completion** — Each story closes with a traceability check + green tests.
5. **Party-mode gates** — Multi-agent review (`bmad-party-mode`) validates PRD fidelity and EKS deployability:
   - After backlog approval → `party-reviews/backlog-roundtable.md`
   - Before each `bmad-dev-story` → `party-reviews/pre-dev-ST-NNN.md`
   - Optional before review → `party-reviews/pre-merge-ST-NNN.md`

---

## Artifact chain

```
intake/01-model-lab/*.md          (uploaded PRD / requirements — immutable input)
        ↓
planning-artifacts/<slug>/prd.md (bmad-prd — if not already supplied)
        ↓
specs/spec-<slug>/SPEC.md         (bmad-spec — kernel + CAP-* IDs)
specs/spec-<slug>/traceability.md (bmad-spec — REQ ↔ CAP ↔ intake section)
        ↓
planning-artifacts/epics/<slug>/  (bmad-create-epics-and-stories)
  epic.md | backlog.md | traceability-matrix.md
        ↓
implementation-artifacts/<slug>/story-ST-*.md  (bmad-create-story — one file per story)
        ↓
code + tests                      (bmad-dev-story — ONE story per chat)
        ↓
review                            (bmad-code-review — traceability audit)
```

---

## ID conventions

| ID | Owner | Example |
|---|---|---|
| `REQ-001` | PRD / intake | "User can export WoE table as CSV" |
| `CAP-001` | SPEC.md | Testable capability derived from REQ(s) |
| `EPIC-001` | backlog.md | User-facing epic |
| `ST-001` | story file | Implementable story (1–3 days) |
| `SUB-001` | story file | Subtask inside a story |

**Rules:**

- Every `CAP-*` cites one or more `REQ-*` in `traceability.md`.
- Every `ST-*` cites one or more `CAP-*` and `REQ-*`.
- Every `SUB-*` is concrete (file, endpoint, component) — no vague "implement feature".

---

## Traceability matrix (required)

File: `_bmad-output/planning-artifacts/epics/<slug>/traceability-matrix.md`

| REQ ID | Intake reference | CAP ID | ST ID | Test file(s) | Status |
|---|---|---|---|---|---|
| REQ-001 | prd.md §3.2 | CAP-001 | ST-001 | tests/test_foo.py | done / pending |

Update **Status** when each story merges. `bmad-code-review` spot-checks this table.

---

## PRD adherence checks

### At spec time (`bmad-spec`)

- [ ] Every numbered requirement in intake/PRD appears as `REQ-*` in `traceability.md`.
- [ ] No `CAP-*` without a `REQ-*` parent (or marked `REQ-TBD` with open question).
- [ ] Non-goals explicitly exclude out-of-scope items from the PRD.

### At backlog time (`bmad-create-epics-and-stories`)

- [ ] Every `REQ-*` maps to at least one `ST-*`.
- [ ] Stories are ordered by dependency (data model → API → UI).
- [ ] Each story has 3–8 `SUB-*` items with file paths.

### At dev time (`bmad-dev-story`)

- [ ] Agent reads intake + PRD + SPEC + **only the current story file**.
- [ ] Implementation cites `ST-*` / `SUB-*` in commit message or PR description.
- [ ] Deviations blocked — if code cannot match PRD, stop and update spec/PRD first.

### At review (`bmad-code-review`)

- [ ] Diff traced to `ST-*` / `REQ-*`.
- [ ] No undocumented behavior.
- [ ] Tests prove each `CAP-*` touched by the story.

---

## When `bmad-quick-dev` is allowed

Only for **single SUB-*** scope (e.g. copy change, one endpoint tweak) with intake path cited. New features **must** use the full chain above.

---

## Related

- [01-model-lab-feature.md](01-model-lab-feature.md) — step-by-step skills
- [_bmad-output/testing/scenario-test-gate.md](../testing/scenario-test-gate.md)
- Templates: `planning-artifacts/templates/epic-backlog-template.md`, `traceability-matrix-template.md`

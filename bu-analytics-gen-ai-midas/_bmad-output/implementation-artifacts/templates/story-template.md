# Story ST-NNN: <title>

**Epic:** EPIC-001  
**Spec:** `_bmad-output/specs/spec-<slug>/SPEC.md`  
**Scenario:** 1 — Model Lab  
**Backlog:** `_bmad-output/planning-artifacts/epics/<slug>/backlog.md`

## Traceability

| Type | IDs |
|---|---|
| Requirements | REQ-001, REQ-002 |
| Capabilities | CAP-001 |
| PRD reference | `planning-artifacts/<slug>/prd.md` §… |
| Intake reference | `intake/01-model-lab/<file>.md` §… |

## Description

_(What this story delivers — must match PRD wording for business rules.)_

## PRD adherence notes

- Business rules that must be implemented exactly: …
- Edge cases from PRD: …
- Explicitly out of scope for this story: …

## Subtasks

| ID | Subtask | Files | Done |
|---|---|---|---|
| SUB-001 | | | [ ] |
| SUB-002 | | | [ ] |
| SUB-003 | Tests: pytest … | `backend/tests/...` | [ ] |
| SUB-004 | Tests: Vitest … | `frontend/src/....test.tsx` | [ ] |

**Rule:** `bmad-dev-story` completes every SUB-* in one chat before closing.

## Acceptance criteria

- [ ] AC1: … (maps to CAP-001 / REQ-001)
- [ ] AC2: …

## Test acceptance criteria (required)

| Layer | Test file(s) | Command |
|---|---|---|
| Backend | | `cd backend && python3 -m pytest -q ...` |
| Frontend | | `cd frontend && npx vitest run ...` |

## SME verification required

| Field | Value |
|---|---|
| **Required?** | yes / no |
| **Reason** | _(e.g. WoE formula, Gini metric, training pipeline)_ |
| **REQ formulas SME must validate** | REQ-001: … |
| **Package path** | `_bmad-output/test-artifacts/sme-reviews/<slug>/ST-NNN/` |

If **yes**: development is not done until human obtains SME sign-off in `sme-signoff.md` (see `testing/sme-verification-gate.md`).

## Definition of done

- [ ] All SUB-* and AC satisfied per PRD/SPEC
- [ ] Tests passing (paste output)
- [ ] **SME sign-off approved** _(if SME verification required = yes)_
- [ ] Traceability matrix row updated for this ST-*
- [ ] `bmad-code-review` completed for this story

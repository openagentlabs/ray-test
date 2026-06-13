# Epic backlog: <feature slug>

> Produced by `bmad-create-epics-and-stories`. Inputs: PRD, `specs/spec-<slug>/SPEC.md`, `traceability.md`.

## Epic EPIC-001: <title>

**User outcome:**  
**REQ IDs:** REQ-001, REQ-002  
**CAP IDs:** CAP-001  

### Story ST-001: <title>

**Description:**  
**Depends on:** —  
**REQ / CAP:** REQ-001 → CAP-001  

#### Subtasks

| ID | Subtask | Files / surface | Done |
|---|---|---|---|
| SUB-001 | | `backend/...` | [ ] |
| SUB-002 | | `frontend/...` | [ ] |
| SUB-003 | Add pytest for … | `backend/tests/test_....py` | [ ] |
| SUB-004 | Add Vitest for … | `frontend/src/....test.tsx` | [ ] |

**Story definition of done:**

- [ ] All SUB-* complete
- [ ] Test AC in `implementation-artifacts/<slug>/story-ST-001.md` satisfied
- [ ] Traceability matrix row updated

---

### Story ST-002: <title>

_(repeat per story)_

---

## Implementation order

1. ST-001  
2. ST-002  
3. …

**Rule:** Run `bmad-dev-story` **once per ST-*** — never multiple stories in one chat.

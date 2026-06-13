# Traceability matrix: <feature slug>

| REQ ID | Source (intake / PRD §) | CAP ID | EPIC | ST ID | SUB IDs | Test evidence | Status |
|---|---|---|---|---|---|---|---|
| REQ-001 | intake/foo.md §2 | CAP-001 | EPIC-001 | ST-001 | SUB-001–003 | `tests/test_....py` | pending |
| REQ-002 | prd.md §4.1 | CAP-002 | EPIC-001 | ST-002 | SUB-001–004 | | pending |

**Status values:** `pending` | `in_progress` | `done` | `deferred` (requires PRD amendment)

**Review:** `bmad-code-review` verifies no `done` row lacks test evidence.

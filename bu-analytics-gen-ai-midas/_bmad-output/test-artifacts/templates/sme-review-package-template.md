# SME review package — <slug> / ST-NNN

**Prepared by:** _(developer / agent)_  
**Date:**  
**For SME:** _(name or role — filled by human before sending)_

## Purpose

Please verify that the **implementation and automated tests** correctly reflect the **business formulas and data-science logic** defined in the PRD/intake for this story.

## Requirements under review

| REQ ID | PRD / intake reference | Formula or logic (quote or summarize) |
|---|---|---|
| REQ-001 | prd.md §… | |

## What we implemented

| Area | Files | Summary |
|---|---|---|
| Production code | `backend/app/services/...` | |
| Tests | `backend/tests/test_....py` | |

## Test evidence (automated — already green)

```
(paste pytest/vitest command + pass count)
```

## What each test asserts (SME focus)

| Test file | Test name | Asserts (formula / metric / behavior) | Matches PRD? (SME) |
|---|---|---|---|
| test_foo.py | test_gini_matches_prd | … | ☐ yes ☐ no ☐ partial |

## Fixtures / sample data

| Fixture | Path | Why SME should care |
|---|---|---|
| sample.parquet | backend/tests/fixtures/… | Expected column X, known outcome Y |

## Open questions for SME

1.  
2.  

---

## SME response (human records in sme-signoff.md)

_Do not edit this section in the package — copy outcome to `sme-signoff.md` after SME replies._

- [ ] **Approved** — logic and tests match PRD  
- [ ] **Changes requested** — see feedback below  

**SME feedback:**

_(paste or link)_

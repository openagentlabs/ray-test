# Scenario test gate (scenarios 1–3)

**Policy:** For Model Lab features, new platform modules, and bug fixes, a BMad workflow is **not complete** until automated tests are **written or updated**, **executed**, and **passing**. Agent responses must include command output (or CI link) proving green tests.

Scenario 4 (EKS scalability) uses the verification checklist in `scenarios/04-eks-scalability.md` (tests + ops evidence).

---

## When the gate applies

| Scenario | Gate triggers | Minimum test types |
|---|---|---|
| **1 Model Lab** | Any change to `backend/`, `frontend/`, or API contracts | Tests must cover **CAP-*** / **REQ-*** for the story; map test files in `traceability-matrix.md` |
| **2 Platform module** | New module code + auth integration | pytest/Vitest for module + **login/logout/401** smoke |
| **3 Bug resolution** | Every fix | **Regression test** reproducing the bug (or guarding the failure mode) |

---

## Commands (run from repo root)

### Backend (pytest)

```bash
cd backend
python3 -m pip install -r requirements.txt -r requirements-dev.txt  # first time only
python3 -m pytest -q
```

**Scoped run** (preferred during dev):

```bash
cd backend
python3 -m pytest -q tests/test_<module>.py
```

**Rules:** `monkeypatch.setenv("RATE_LIMIT_ENABLED", "false")`; auth via `dependency_overrides`; clear overrides after each test. See `project-context.md` → Testing Rules — Backend.

### Frontend (Vitest)

```bash
cd frontend
npm ci   # first time only
npm run test
```

**Scoped run:**

```bash
cd frontend
npx vitest run src/path/to/Component.test.tsx
```

**Rules:** loading / empty / error states for data components; co-located `*.test.tsx`. See `project-context.md` → Testing Rules — Frontend.

### Combined helper script

```bash
bash _bmad-output/testing/run-scenario-tests.sh
bash _bmad-output/testing/run-scenario-tests.sh --backend-only tests/test_chunked_upload.py
bash _bmad-output/testing/run-scenario-tests.sh --frontend-only src/components/Foo.test.tsx
```

---

## Skill order with tests (scenarios 1–3)

| Phase | Skill | Test responsibility |
|---|---|---|
| Story | `bmad-create-story` | Story file **must** include "Test acceptance criteria" with file paths + commands |
| Implement | `bmad-dev-story` / `bmad-quick-dev` | Implement code **and** tests; run scoped pytest/Vitest before finishing |
| QA (recommended) | `bmad-qa-generate-e2e-tests` | Add API/E2E coverage when story AC is thin or UI-heavy |
| Review | `bmad-code-review` | Reject if tests missing, not run, or failing |
| **Gate** | _(agent or human)_ | Full or scoped suite green; paste summary in chat/PR |

**Definition of done (1–3):** Story AC met + tests pass + (**SME approved** if formula/ML logic — see [sme-verification-gate.md](sme-verification-gate.md)) + `bmad-code-review` clean.

---

## SME verification (formulas & data science)

When tests assert **business formulas**, **training**, **metrics**, or **feature-engineering** logic:

1. Agent creates `_bmad-output/test-artifacts/sme-reviews/<slug>/ST-NNN/sme-review-package.md`
2. **Developer shares** package + tests with **SME**
3. Developer records `sme-signoff.md` — **Verdict: approved** required before story is done
4. If **changes requested** → fix → re-test → SME re-review

Agents must **stop** after creating the package and instruct the human to contact the SME.

---

## What to paste when claiming "done"

```
## Test evidence
- Backend: `cd backend && python3 -m pytest -q tests/test_foo.py` → N passed
- Frontend: `cd frontend && npm run test` → N passed (or scoped file)
- Regression: tests/test_bug_mid123.py covers MIDAS-123
```

---

## TEA module (optional depth)

TEA is installed (`_bmad/tea/config.yaml`). Outputs go to `_bmad-output/test-artifacts/`. Use when you need formal test design or traceability beyond unit tests — not a substitute for the pytest/Vitest gate above.

---

## Related

- `_bmad-output/project-context.md` — testing rules
- `_bmad/custom/bmad-*.toml` — workflow overrides enforcing this gate
- `_bmad-output/How to use BMAD for each scenario.md`

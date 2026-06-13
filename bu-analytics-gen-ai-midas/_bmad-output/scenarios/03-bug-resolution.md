# Scenario 3 — Bug resolution

## Scope

| Bug class | Examples | Primary surfaces |
|---|---|---|
| **UI** | Wrong chart, stepper state, dark mode, virtualized table glitches | `frontend/src/`, `apiInterceptor.ts` |
| **Production / deploy** | Helm values, pipeline failure, pod crash loop, secrets | `deploy/`, Jenkins logs |
| **Backend formulas / ML** | Metric miscalculation, training pipeline, feature engineering | `backend/app/services/`, `backend/tests/` |
| **Security** | Auth bypass, PII in logs, IDOR | Middleware, `project-context` financial rules |

## Preconditions

Place repro artifacts in `_bmad-output/intake/03-bug-resolution/<ticket-id>/`:

- Steps to reproduce, expected vs actual
- Screenshots, HAR, or API request/response (redact tokens)
- Jenkins build number / stage (deploy bugs)
- Log excerpts (CloudWatch) — no raw PII

## Workflow steps

### 1. Investigate (`bmad-investigate`)

**Prompt:**

```
Use bmad-investigate for bug <id>: <one-line summary>.
Evidence in _bmad-output/intake/03-bug-resolution/<id>/.
Classify: UI | backend | security | deploy. Grade findings by evidence strength.
Ground in repo paths; read project-context.md for constraints.
```

**Done when:** Ranked root cause hypothesis with file references and suggested fix scope.

### 2. Fix

| Size | Skill |
|---|---|
| Small, localized | `bmad-quick-dev` |
| Needs story/AC | `bmad-create-story` → `bmad-dev-story` |

**Prompt:**

```
Use bmad-quick-dev (or bmad-dev-story with story <path>).
Fix bug <id> per investigation. Minimal diff only. Add regression test.
Follow _bmad-output/project-context.md and _bmad-output/testing/scenario-test-gate.md.
Run scoped pytest/Vitest until green before finishing.
```

### 3. Edge cases (`bmad-review-edge-case-hunter`) — optional

For state conflicts, concurrency, or formula boundary values.

### 4. Review (`bmad-code-review`)

Mandatory for security and financial-data bugs.

### 5. Operational verification

| Bug class | Tool |
|---|---|
| Deploy / IaC | `tf_validate` then Jenkins `jenkins_run` |
| Runtime in VPC | Jumpbox diagnostics per `.cursor/rules/debuging/debug.mdc` (read-only unless user approves) |

## Escalation

| Situation | Path |
|---|---|
| Root cause is memory / large files | Open scenario 4 architecture pass |
| Needs ADR (new AWS service, public endpoint) | Stop — draft `docs/adr/` before fix |
| Flaky repro | `bmad-party-mode` with architect + dev agents |

## Completion checklist

- [ ] Repro fixed with **regression test** (named for ticket id when possible)
- [ ] **Regression test executed and passing** ([scenario-test-gate.md](../testing/scenario-test-gate.md))
- [ ] **SME sign-off** if fix involves formulas/metrics ([sme-verification-gate.md](../testing/sme-verification-gate.md))
- [ ] Security bugs reviewed with `bmad-code-review`
- [ ] Deploy bugs: pipeline SUCCESS in target env
- [ ] No unrelated refactors in diff

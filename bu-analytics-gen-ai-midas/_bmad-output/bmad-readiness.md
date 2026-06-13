# BMad readiness — MIDAS

Last updated: 2026-05-27

## Infrastructure prep (ready)

| Item | Status | Location |
|---|---|---|
| BMad 6.8.0 install | Done | `_bmad/_config/manifest.yaml` |
| Project context + scenario routing | Done | `_bmad-output/project-context.md` |
| Workflow map + user guide | Done | `_bmad-output/bmad-workflow-map.md`, `How to use BMAD for each scenario.md` |
| Intake folders | Done | `_bmad-output/intake/01–04/` |
| Planning templates (PRD, UX, architecture) | Done | `_bmad-output/planning-artifacts/templates/` |
| Story template + test AC section | Done | `_bmad-output/implementation-artifacts/templates/` |
| Scenario test gate (1–3) | Done | `_bmad-output/testing/scenario-test-gate.md` |
| Test runner script | Done | `_bmad-output/testing/run-scenario-tests.sh` |
| Team workflow overrides (test-first) | Done | `_bmad/custom/bmad-*.toml` |
| Scenario 1 PRD traceability + epic backlog gate | Done | `scenarios/01-requirements-traceability.md`, custom `bmad-prd/spec/create-epics/code-review.toml` |
| Scenario 1 party-mode (PRD + EKS roundtables) | Done | `bmad-party-mode.toml`, `templates/party-review-synthesis-template.md`, phases C★/D★/F★ in guides |
| SME verification (formulas / ML tests) | Done | `testing/sme-verification-gate.md`, SME templates, story template + custom overrides |
| TEA module + test-artifacts dirs | Done | `_bmad/tea/config.yaml`, `_bmad-output/test-artifacts/` |

## Per-feature work (created on first use)

These are **not** pre-generated — run skills with intake in a **fresh chat**:

| Artifact | Skill | When |
|---|---|---|
| `specs/spec-<slug>/` | `bmad-spec` | Scenario 1, 2, 4 feature start |
| `planning-artifacts/*.md` | `bmad-prd`, `bmad-ux`, `bmad-create-architecture` | As needed |
| `implementation-artifacts/<story>.md` | `bmad-create-story` | Before dev |
| Code + tests | `bmad-dev-story` | Implementation |
| E2E / test design | `bmad-qa-generate-e2e-tests` | Optional depth |

## Optional / gaps

| Item | Status | Action |
|---|---|---|
| `_bmad/_config/bmad-help.csv` | Missing | Re-run BMad installer or use `bmad-skill-catalog.md` |
| `bmad-check-implementation-readiness` | Not run | Run before a large epic: `Use bmad-check-implementation-readiness` |
| `bmad-sprint-planning` | Not run | Run when team wants sprint-status.yaml |
| Local pytest/Vitest | Verify on your machine | `bash _bmad-output/testing/run-scenario-tests.sh` |

## Test gate policy

Scenarios **1–3**: agents must not claim completion without passing tests. Enforced in `_bmad/custom/bmad-dev-story.toml`, `bmad-quick-dev.toml`, and docs.

Scenario **4**: tests + ops checklist per `scenarios/04-eks-scalability.md`.

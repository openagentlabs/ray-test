# BMad workflow map — MIDAS (EXLDecision.AI)

BMad **6.8.0** is installed (`_bmad/_config/manifest.yaml`). Skills live in `.agents/skills/`. Outputs default to `_bmad-output/` (`_bmad/config.toml` → `output_folder`).

> **Gap:** `_bmad/_config/bmad-help.csv` is not present in this repo (installer did not emit the catalog CSV). Skill routing below is built from installed skills and `bmad-manifest.json` fragments. Use `_bmad-output/bmad-skill-catalog.md` as the local index. Run the BMad installer again if you need the official CSV.

## Installed modules

| Module | Config | Purpose |
|---|---|---|
| `core` | `_bmad/core/config.yaml` | Output folder, language |
| `bmm` | `_bmad/bmm/config.yaml` | Planning + implementation artifact paths |

| Path variable | Resolves to |
|---|---|
| `{output_folder}` | `_bmad-output/` |
| `{planning_artifacts}` | `_bmad-output/planning-artifacts/` |
| `{implementation_artifacts}` | `_bmad-output/implementation-artifacts/` |
| `{project_knowledge}` | `docs/` |

## Four scenarios — phase order and completion signals

### Scenario 1 — Model Lab feature build/improve

**New features** — strict PRD traceability ([01-requirements-traceability.md](scenarios/01-requirements-traceability.md)):

| Phase | Skill(s) | Required? | Output / done when |
|---|---|---|---|
| Intake | _(human)_ | Yes | `_bmad-output/intake/01-model-lab/` |
| PRD | `bmad-prd` | If intake not numbered PRD | `planning-artifacts/<slug>/prd.md` with `REQ-*` |
| Contract | `bmad-spec` | **Yes** | `specs/spec-<slug>/SPEC.md` + `traceability.md` |
| Backlog | `bmad-create-epics-and-stories` | **Yes** (new features) | `epics/<slug>/backlog.md` + `traceability-matrix.md` |
| Approval | _(human)_ | **Yes** | Backlog approved |
| Roundtable | `bmad-party-mode` | **Yes** | `party-reviews/backlog-roundtable.md` (PRD + EKS) |
| Stories | `bmad-create-story` | **Yes** | One `story-ST-*.md` per story |
| Pre-dev RT | `bmad-party-mode` | **Yes** (per ST) | `party-reviews/pre-dev-ST-NNN.md` |
| UX | `bmad-ux` | If UI-heavy | Aligned to REQ/CAP |
| Implement | `bmad-dev-story` | **Yes** | **One ST per chat**; all SUB-*; PRD logic exact; tests green |
| QA | `bmad-qa-generate-e2e-tests` | Optional | Extra coverage |
| Review | `bmad-code-review` | **Yes** | Traceability audit + tests |
| Checkpoint | `bmad-checkpoint-preview` | Optional | Demo before merge |

**Small improvement:** `bmad-create-story` → `bmad-dev-story` → review (still REQ-linked).

**Completion signal:** All REQ covered in matrix, backlog ST done, tests green, review passed.

---

### Scenario 2 — New platform module

| Phase | Skill(s) | Required? | Output / done when |
|---|---|---|---|
| Intake | _(human)_ | Yes | `_bmad-output/intake/02-platform-module/` |
| Architecture | `bmad-create-architecture` | Yes | Architecture doc in `{planning_artifacts}`; auth boundary = Cognito login/logout only |
| Contract | `bmad-spec` | Yes | Spec folder; **Non-goals** must exclude MIDAS app internals |
| PRD (if large) | `bmad-prd` | Optional | PRD in `{planning_artifacts}` |
| Story + dev | `bmad-create-story` → `bmad-dev-story` | Yes | Module + tests + auth smoke (401) |
| Review | `bmad-code-review` | Recommended | Security + boundary; tests must pass |

**Completion signal:** Module runs with platform auth only; **tests green**; no Model Lab imports; ADR if new AWS surface.

---

### Scenario 3 — Bug resolution

| Phase | Skill(s) | Required? | Output / done when |
|---|---|---|---|
| Intake | _(human)_ | Yes | Repro steps / logs in `_bmad-output/intake/03-bug-resolution/` |
| Investigate | `bmad-investigate` | Yes (non-trivial) | Evidence-graded findings |
| Fix | `bmad-dev-story` or `bmad-quick-dev` | Yes | Minimal diff + **regression test green** |
| Edge cases | `bmad-review-edge-case-hunter` | Optional | Unhandled paths listed |
| Review | `bmad-code-review` | Recommended | No regressions |
| Deploy / IaC | `jenkins_run`, `tf_validate` | If deploy/infra bug | Pipeline green / Checkov clean |

**Completion signal:** Repro fixed, **regression test run and passing**, review done; prod — Jenkins verify.

**Bug class routing**

| Class | Lead skill | MIDAS touchpoints |
|---|---|---|
| UI | `bmad-investigate` → `bmad-quick-dev` | `frontend/src/`, `apiInterceptor.ts` |
| Backend formulas / ML | `bmad-investigate` | `backend/app/services/`, tests with fixture parquet |
| Security | `bmad-investigate` + `bmad-code-review` | Auth middleware, PII rules in project-context |
| Deploy / readiness | `bmad-investigate` | `deploy/`, Helm, Jenkins; `tf_validate` for Terraform |

---

### Scenario 4 — EKS scalability (large CSV, multi-user)

| Phase | Skill(s) | Required? | Output / done when |
|---|---|---|---|
| Intake | _(human)_ | Yes | Load model + SLOs in `_bmad-output/intake/04-eks-scalability/` |
| Research | `bmad-technical-research` | Recommended | Options for chunking, S3, Redis locks, HPA |
| Architecture | `bmad-create-architecture` | Yes | Pod/worker memory math, data flow diagram |
| Spec | `bmad-spec` | Recommended | Constraints cite 5 GB min / 20 GB target |
| Implement | `bmad-dev-story` | Yes | Chunked/streaming paths, bounded caches |
| Verify | Tests + ops checklist (scenario file) | **Required** | Perf tests, concurrent-user notes |
| Review | `bmad-code-review` | Yes | Memory and cross-pod called out |

**Completion signal:** Tests prove no full-file load; operational note covers 5 and 20 user targets; Helm/resource impact documented.

---

## Agent personas (optional facilitation)

| Agent skill | Persona | Use when |
|---|---|---|
| `bmad-agent-analyst` | Mary | Ambiguous requirements before spec |
| `bmad-agent-pm` | John | PRD / prioritization |
| `bmad-agent-architect` | Winston | Architecture debates (scenario 2, 4) |
| `bmad-agent-dev` | Amelia | Pair on implementation style |
| `bmad-agent-ux-designer` | Sally | Model Lab UI flows |
| `bmad-agent-tech-writer` | Paige | User-facing docs after ship |

## Anytime utilities

| Skill | Use |
|---|---|
| `bmad-help` | "What next?" — reads artifacts + config (CSV if present) |
| `bmad-party-mode` | **Scenario 1:** backlog + pre-dev PRD/EKS gates; also hard decisions (2, 4) |
| `bmad-advanced-elicitation` | Deep critique of a spec or design |
| `bmad-correct-course` | Scope change mid-sprint |
| `bmad-generate-project-context` | Refresh rules after stack change |
| `bmad-document-project` | Brownfield discovery |

## Operational skills (not BMad — MIDAS repo)

| Skill | Scenario |
|---|---|
| `jenkins_run` / `jenkins` | Deploy after merge |
| `tf_validate` | Terraform/Checkov before push |
| `git_pull_commit_push` | Ship workflow |

## Team customizations (test gate)

| File | Effect |
|---|---|
| `_bmad/custom/bmad-spec.toml` | REQ/CAP traceability companion |
| `_bmad/custom/bmad-prd.toml` | Numbered REQ-* from intake |
| `_bmad/custom/bmad-create-epics-and-stories.toml` | Backlog before dev |
| `_bmad/custom/bmad-code-review.toml` | PRD adherence audit |
| `_bmad/custom/bmad-party-mode.toml` | PRD + EKS roundtable rules |
| `_bmad/custom/bmad-dev-story.toml` | Require green tests + strict PRD |
| `_bmad/custom/bmad-create-story.toml` | Mandatory test AC in stories |
| `_bmad/custom/bmad-quick-dev.toml` | Regression + green tests for fixes |
| `_bmad/custom/config.toml` | Amelia/Sally MIDAS personas |

## Related files

- `_bmad-output/bmad-readiness.md` — setup vs per-feature artifacts
- `_bmad-output/testing/scenario-test-gate.md` — scenarios 1–3 test policy
- `_bmad-output/scenario-skill-matrix.md` — matrix view
- `_bmad-output/scenarios/*.md` — per-scenario steps
- `_bmad-output/How to use BMAD for each scenario.md` — user guide
- `_bmad-output/spec-kernel.md` — SPEC kernel reference

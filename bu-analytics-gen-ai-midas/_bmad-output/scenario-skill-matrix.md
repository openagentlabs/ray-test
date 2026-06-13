# Scenario → skill matrix

Skills listed are installed under `.agents/skills/` (BMad 6.8.0). Invoke by name in Cursor (e.g. "use **bmad-spec**"). Prefer a **fresh chat** per skill.

| Scenario | Goal | Primary skills | Supporting skills | Preconditions | Expected outputs | Fresh-context note |
|---|---|---|---|---|---|---|
| **1 Model Lab** | Ship feature with **strict PRD adherence** + **EKS-safe** design | `bmad-prd`, `bmad-spec`, `bmad-create-epics-and-stories`, **`bmad-party-mode`**, `bmad-create-story`, `bmad-dev-story` | `bmad-agent-*`, `bmad-ux`, `bmad-code-review`, `bmad-qa-generate-e2e-tests` | Intake + backlog approved + **party backlog review** | PRD, SPEC, backlog, **party-reviews/**, stories, code, tests | Party-mode before dev **per ST**; one ST per dev chat |
| **2 Platform module** | New module with auth-only platform tie-in | `bmad-create-architecture`, `bmad-spec`, `bmad-dev-story` | `bmad-prd`, `bmad-create-story`, `bmad-code-review` | Intake in `intake/02-platform-module/` | Architecture + spec + module + **tests green** | Architecture separate from dev |
| **3 Bug resolution** | Fix UI, formula, security, or deploy issue | `bmad-investigate`, `bmad-quick-dev` or `bmad-dev-story` | `bmad-review-edge-case-hunter`, `bmad-code-review`, `jenkins_run`, `tf_validate` | Repro in `intake/03-bug-resolution/` | Fix + **regression test green** | Investigate then implement |
| **4 EKS scalability** | 5→20 users, 5–20 GB CSV per user, AWS/EKS | `bmad-technical-research`, `bmad-create-architecture`, `bmad-dev-story` | `bmad-spec`, `bmad-code-review` | Load targets in `intake/04-eks-scalability/` | ADR if needed, tests + ops verification checklist | Research/architecture before dev |

## Skill inventory (installed)

| Skill | Typical scenario(s) |
|---|---|
| `bmad-help` | All |
| `bmad-spec` | 1, 2, 4 |
| `bmad-prd` | 1 (large), 2 |
| `bmad-create-story` | 1, 2 |
| `bmad-dev-story` | 1, 2, 4 |
| `bmad-quick-dev` | 1, 3 (small fixes) |
| `bmad-code-review` | 1, 2, 3, 4 |
| `bmad-investigate` | 3, 3→4 if perf regression |
| `bmad-create-architecture` | 2, 4 |
| `bmad-technical-research` | 4 |
| `bmad-ux` | 1 |
| `bmad-qa-generate-e2e-tests` | 1 (optional; after dev) |
| `bmad-review-edge-case-hunter` | 3, 4 |
| `bmad-checkpoint-preview` | 1 (pre-merge) |
| `bmad-generate-project-context` | Maintenance |
| `bmad-document-project` | Onboarding |
| `bmad-check-implementation-readiness` | Before epic execution |
| `bmad-create-epics-and-stories` | **1 (required for new features)** |
| `bmad-prd` | 1 (when intake needs formal PRD) |
| `bmad-sprint-planning` / `bmad-sprint-status` | Team cadence |
| `bmad-party-mode` | **1 (backlog + pre-dev gates)**; 2/4 for architecture debates |
| `bmad-advanced-elicitation` | Hard decisions |
| `bmad-prfaq` | Early concept (menu **WB** in manifest) |
| `bmad-agent-*` | Facilitation by role |

## Deprecated (do not start new work)

| Skill | Replacement |
|---|---|
| `bmad-create-prd` | `bmad-prd` (create) |
| `bmad-edit-prd` | `bmad-prd` (update) |
| `bmad-validate-prd` | `bmad-prd` (validate) |

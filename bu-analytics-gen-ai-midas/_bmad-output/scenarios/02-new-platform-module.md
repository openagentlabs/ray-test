# Scenario 2 — New platform module

## Scope

A **new module** that will live on the MIDAS platform but is **not** part of the Model Lab stepper or core analytics codebase. The only required platform integration is **user login/logout** (AWS Cognito / existing auth flows).

## Boundary rules (non-negotiable)

| Allowed | Forbidden |
|---|---|
| Cognito hosted UI / callback patterns (`frontend/src/pages/AuthCallback.tsx`, `authService.ts`) | Importing Model Lab steps, `ModelBuilder`, dataset managers |
| `Depends(get_current_user_dependency)` or equivalent session validation | Calling MIDAS business APIs except auth/session |
| Shared infra: EKS deploy, Secrets Manager, private VPC | Coupling to `exldecision-ai-modellab` DB tables without ADR |
| New Helm chart or service under `deploy/ecs-app/helm/` (with pipeline) | Editing `ai_gateway/**` |

Document the module boundary in the architecture artifact **before** `bmad-dev-story`.

## Preconditions

1. Intake in `_bmad-output/intake/02-platform-module/` (vision, users, auth assumption, deploy target).
2. Stakeholder agrees: **auth-only** dependency on MIDAS app code.

## Workflow steps

### 1. Solution architecture (`bmad-create-architecture`)

**Prompt:**

```
Use bmad-create-architecture for a new platform module: <name>.
Constraints: AWS us-east-1, private VPC, EKS-deployable, Cognito login/logout ONLY from MIDAS — no other MIDAS app imports.
Output to _bmad-output/planning-artifacts/.
Include: deployment unit (new chart vs existing), data stores (if any), and ADR triggers.
```

### 2. Machine contract (`bmad-spec`)

**Prompt:**

```
Use bmad-spec. Slug: module-<name>.
Input: architecture doc + intake/02-platform-module/.
Non-goals must list all MIDAS app areas we will NOT reference.
```

### 3. PRD (optional — `bmad-prd`)

Use for multi-release modules or external stakeholders.

### 4. Story + implementation

Same pattern as scenario 1: `bmad-create-story` → `bmad-dev-story`.

**Prompt hint for dev:**

```
Implement module <name> per spec. Auth: reuse Cognito patterns only — document which routes/files are touched.
Do not import from backend/app/services except auth/session utilities if already extracted; prefer new package path <module>/.
```

### 5. Tests (required)

Before review, run per [scenario-test-gate.md](../testing/scenario-test-gate.md):

- Module unit/integration tests (pytest and/or Vitest)
- Auth smoke: login, logout, **401** without token

### 6. Review (`bmad-code-review`)

Emphasize **import graph** and **security** (no cross-tenant data without `organisation_id` checks if module stores data). Reject if tests missing or failing.

## Completion checklist

- [ ] Architecture documents auth-only boundary
- [ ] ADR filed if new data store or AWS service
- [ ] Separate deploy path documented (Helm/Jenkins)
- [ ] No Model Lab or monolithic route dependencies
- [ ] **Tests written/updated, executed, and passing** (including Cognito login, logout, 401)
- [ ] `bmad-code-review` completed

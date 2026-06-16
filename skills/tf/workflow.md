# tf — workflow (authoritative for this skill)

> **Read policy:** Open **only** when executing the **tf** skill workflow (after **`SKILL.md`** mandatory rules). **Do not** read **`reference.md`** until a **RUN** row below requires it, or **ON_ERROR** needs the [error map](reference.md#common-error--jmp-map).

Execute **`WorkflowStart:`** → … → **`WorkflowEnd:`**. **`→`** = default next stage.

| Stage | Do | Branch / Jmp |
|-------|----|--------------|
| **`WorkflowStart:`** | Load intent (checks\|plan\|apply\|destroy\|output\|state), **`infra/`** touches, init ran? **STORE:** `intent`, `tf_root=infra/aws/aws_tf`, `apply_approved=false`, `destroy_approved=false`. **If tf-tool/registry:** **RUN** `cd .cursor/tools/tf-tool && uv run tf-tool doctor` first (env check + spinner UI) | → **`WorkflowGetDate:`** |
| **`WorkflowGetDate:`** | **`started_at`** ISO-8601 UTC; optional **`solution_date`** from **`infra/aws/aws_tf/terraform.tfvars`** | → **`WorkflowPreflight:`** |
| **`WorkflowPreflight:`** | **`cd infra/aws/aws_tf`**. If apply/destroy/first AWS → **RUN** [pre-flight](reference.md#pre-flight-aws-identity). If no **`.terraform/`** or providers changed → need init. **ON_ERROR** wrong account → stop until user override per **infra.mdc** | → **`WorkflowInit:`** |
| **`WorkflowInit:`** | If not initialized → **RUN** [init](reference.md#init). Else log "init skipped". **ON_ERROR** backend/auth → report; after user fix **`Jmp: WorkflowPreflight`** | → **`WorkflowFmt:`** |
| **`WorkflowFmt:`** | **RUN** [fmt](reference.md#fmt). If files changed → note paths in handoff | → **`WorkflowValidate:`** |
| **`WorkflowValidate:`** | **RUN** [validate](reference.md#validate). **ON_ERROR** → fix HCL → **`Jmp: WorkflowFmt`**. Validate-only + full checks → **`Jmp: WorkflowCheckov`**. Validate-only only → **`Jmp: WorkflowHandoff`**. Else → **`WorkflowPlan:`** | |
| **`WorkflowPlan:`** | **RUN** [plan](reference.md#plan). **POSTCONDITION:** exit 0 or user saw delta. **ON_ERROR** lock → **`Delay: 10s`**, **`Jmp: WorkflowPlan`** (≤3). Plan-only or apply → **`Jmp: WorkflowCheckov`** (apply → **`WorkflowApplyGate`** after). Else → **`Jmp: WorkflowHandoff`** | |
| **`WorkflowCheckov:`** | Before apply, after infra edits, or "all tests" → **RUN** [checkov](reference.md#checkov) + traffic-light per **checkov-tool.mdc**. Critical + no risk accept → **`Jmp: WorkflowHandoff`**. Apply intent → **`WorkflowApplyGate`**. Else → **`Jmp: WorkflowHandoff`** | |
| **`WorkflowApplyGate:`** | **ASK:** deploy now? (yes/no). No → **`Jmp: WorkflowHandoff`**. Yes → **`apply_approved=true`** → **`WorkflowApply:`** | |
| **`WorkflowApply:`** | **PRE:** **`apply_approved`** + Checkov OK or risk accepted. **RUN** [apply](reference.md#apply). **ON_ERROR** HCL → **`Jmp: WorkflowFmt`**. Lock → **`Delay: 10s`**, **`Jmp: WorkflowApply`** (≤3) | → **`WorkflowOutput:`** |
| **`WorkflowOutput:`** | **RUN** [output](reference.md#output) (`-json` if parsing) | → **`WorkflowHandoff:`** |
| **`WorkflowHandoff:`** | Summarize: **`started_at`**, intent, stages run/skipped, fmt/validate/plan/apply, Checkov, outputs, next step | → **`WorkflowEnd:`** |
| **`WorkflowEnd:`** | User knows pass/fail and whether apply ran. **STOP** — no apply without new request + fresh **`WorkflowStart:`** | |

---

## Intent → minimum stages

| Intent | Stages |
|--------|--------|
| fmt + validate | Start → … → Validate → Handoff → End |
| plan | … → Plan → Checkov (if infra touched) → Handoff → End |
| apply | Full through Apply → Output → Handoff → End |
| validate only | Stop after Validate → Handoff → End |
| destroy | Plan (destroy) → DestroyGate → Destroy → Handoff → End — see [destroy](reference.md#destroy) |

## Optional paths (when user asks)

| User intent | Notes |
|-------------|-------|
| Plan + security only | Through **`WorkflowCheckov:`**; no apply |
| Destroy | **`WorkflowDestroyGate:`** → **`WorkflowDestroy:`**; mirror apply gate |
| State / taint | [state](reference.md#state-inspect--troubleshoot); never apply without plan |
| Module-scoped plan | [plan -target](reference.md#plan) |

## Jmp / Delay (this workflow)

| Label / Delay | Use |
|---------------|-----|
| **`WorkflowStart:`** | Full restart after HCL fixes |
| **`WorkflowFmt:`** | Re-fmt + re-validate |
| **`WorkflowPlan:`** / **`WorkflowApply:`** | Lock retry after **`Delay: 10s`** (≤3) |
| **`WorkflowHandoff:`** | Early exit |
| **`WorkflowPreflight:`** | After creds/backend fix |
| **`Delay: 30s`** | Backend propagation |
| **`Delay: 2m`** | Rare AWS consistency (note in handoff) |

DSL semantics (generic): **[workflow-reference.md](../_shared/workflow-reference.md)** — read only if unclear.

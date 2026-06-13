---
name: kt-tf-add-resource
description: >-
  Adds or extends MIDAS AWS infrastructure in Terraform per project rules: discovers
  or creates modules under deploy/ecs-app/modules/, registers them in deploy/ecs-app/,
  wires IAM when needed, and asks the user when requirements are ambiguous.
  Use when the user mentions kt_tf_add_resource, adding Terraform resources, new AWS
  modules for ecs-app, or extending existing modules (e.g. S3, SQS, KMS patterns).
---

# kt_tf_add_resource - Add AWS resources via Terraform (MIDAS)

## When to apply

User invokes this skill, asks to add Terraform/AWS resources for **MIDAS**, or references **`kt_tf_add_resource`**. Scope: **`deploy/ecs-app/`** root and **`deploy/ecs-app/modules/<purpose>/`** only (per pipeline).

## Non-negotiable rules source

**Read and follow** workspace rules in `.cursor/rules/solution_const.mdc` for every change. If that file conflicts with this skill, **solution_const.mdc wins**.

Compressed reminders (do not skip reading the full rule file):

- **Region:** `us-east-1` only for MIDAS; no extra regions without explicit product + pipeline change.
- **Security:** Corporate account - private by default, least-privilege IAM, encryption where supported, consistent tags, no hard-coded secrets; document security-impacting choices in **module comments** (or other text the user asked for), per **solution_const.mdc**.
- **Modules:** `deploy/ecs-app/modules/<purpose>/` - short, lowercase folder per concern; **registration** = `module` block in `deploy/ecs-app/*.tf`.
- **Pipeline:** Root applied by Jenkins is **`deploy/ecs-app/`** only; EKS lives under **`deploy/ecs-app/modules/eks/`**. Do not put new MIDAS modules under `deploy/ecr_ssm/`, etc., unless the pipeline is extended.
- **Wiring:** New resource types may need **`deploy/deploy_role/iam-policy/`** updates before apply; new root variables need **defaults** unless `Jenkinsfile_Deploy_App` passes `-var`; **no second backend** inside modules. **No** required **`deploy/README.md`** updates for new module folders (see **solution_const.mdc**).
- **Network:** VPC/subnets are centrally managed - do not create IGW/NAT/public subnets without approval; prefer variables/data sources for subnet IDs; see solution_const.mdc for DEV snapshot hints.

## Workflow

1. **Clarify intent (minimal questions first)**  
   Capture: AWS service/resource type, purpose, environment naming expectations, and whether this belongs in an **existing** concern (e.g. extend `s3`) or a **new** `<purpose>` folder.

2. **Discover existing module**  
   List `deploy/ecs-app/modules/` (and grep `deploy/ecs-app/*.tf` for `source = "./modules/`).  
   - **Module exists for this concern:** extend `main.tf` / `variables.tf` / `outputs.tf`; adjust root `module` inputs in the appropriate `*.tf`.  
   - **No module:** create a new folder under `deploy/ecs-app/modules/<purpose>/` (see **Gold-standard module layout** below).

3. **When to stop and ask the user**  
   Ask before implementing if any of these are unclear or product-specific: public vs private exposure, cross-account access, exact resource names/tags, subnet/SG placement, KMS vs AWS-managed keys, whether a new IAM capability is allowed for **midas-deployer-role**, cost/retention, or any choice that would violate solution_const.mdc without explicit approval.

4. **Implement**  
   - Add AWS resources with restrictive defaults; use opt-in variables only when the user or solution_const.mdc allows and document.  
   - Add or update **IAM policy statements** in `deploy/deploy_role/iam-policy/midas-deployer-policy-001` … `010`, spreading changes across the ten files; keep each under **6,144** characters; do not add an eleventh policy without a quota increase (see `.cursor/rules/solution_policy.mdc` and `deploy/deploy_role/main.tf`).  
   - Run **`terraform fmt -recursive`** on `deploy/ecs-app` and **`terraform validate`** from `deploy/ecs-app` when backend/init allows.

5. **Post-task report (required)**  
   After all edits, output the **TASK REPORT** in the format in **Post-task report** below. Treat it as mandatory. For stack-specific hints (Terraform IAM, validate), align with **kt_debug**-style bullets where relevant.

## Gold-standard module layout (new `<purpose>`)

Create under `deploy/ecs-app/modules/<purpose>/`:

| File | Purpose |
|------|---------|
| `versions.tf` | `terraform` block + `required_providers` for `hashicorp/aws` (match sibling modules, e.g. `>= 1.1`, `aws` `>= 4.0`). |
| `variables.tf` | Prefer `aws_account_id`, `environment`, `aws_region` (default `us-east-1`) + resource-specific inputs with descriptions. |
| `main.tf` | AWS resources; locals for naming/tags; security-first defaults. |
| `outputs.tf` | Export ARNs/ids consumers need. |

Register in **`deploy/ecs-app/`** (e.g. new `sqs.tf` or existing file):

```hcl
module "<purpose>" {
  source = "./modules/<purpose>"

  aws_account_id = var.aws_account_id
  environment    = var.environment
  aws_region     = var.aws_region
  # ... module-specific variables
}
```

Do **not** add a nested `backend` in the module.

## Post-task report

Use **exactly** this structure after completing the Terraform work. Entire report **≤ 60 lines**. No prose paragraphs-bullets, tables, or single lines only. Current local date/time in the header.

```
╔══════════════════════════════════════════════════════════════╗
║  TASK REPORT                                    [DATE/TIME]  ║
╚══════════════════════════════════════════════════════════════╝

▸ TASK
  One-line summary of what was asked.

▸ STATUS
  ✅ COMPLETE  |  ⚠️ PARTIAL  |  ❌ BLOCKED
  (choose one - add a single sentence reason if not COMPLETE)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

▸ WHAT WAS DONE
  • [Action verb] - [what changed] - [file/location]
  (max 7 bullets; group small changes)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

▸ FILES CHANGED
  Modified  : path/to/file.ext
  Created   : path/to/file.ext
  Deleted   : path/to/file.ext

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

▸ DECISIONS & TRADE-OFFS
  • [Decision] → [why, ≤10 words]
  (omit if none)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

▸ RISKS & WATCH-OUTS
  🔴 HIGH    : [issue] - [mitigation]
  🟡 MEDIUM  : [issue] - [mitigation]
  🟢 LOW     : [issue] - [no action]
  (omit levels that do not apply)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

▸ NEXT STEPS
  □ [Actionable item]
  (max 4; if none: "None - ready to merge/deploy")

══════════════════════════════════════════════════════════════
```

### Report rules

| Rule | Detail |
|------|--------|
| **Action verbs** | WHAT WAS DONE: start bullets with Added / Updated / Created / Deleted / Fixed / Refactored / Removed / Migrated |
| **Paths** | Repo-relative paths only |
| **Honesty** | Partial/blocked status and real risks (e.g. skipped validate, IAM not yet applied) |
| **No filler** | No “successfully completed”, “as requested”, etc. |

## Optional: combine with kt_debug

If the user also wants **kt_debug** branding, the report above is the same gold-standard handoff; optional cross-reference: `.cursor/skills/kt_debug/SKILL.md`.

---
name: aws-s3-create
description: >-
  Guides interactive discovery for provisioning an AWS S3 bucket using the
  Arb Sherpa Terraform child module template under `infra/tf_lib/s3`
  (copy into `infra/aws_tf/modules/…`, wire from `infra/aws_tf/main.tf`).
  Resolves owning application service (`frontend`, `iam.service`,
  `solutions.svc`) from the user’s words when possible; otherwise asks
  once, then updates `infra/deployed/.../services/<service>/terraform/aws/s3/`
  and module wiring. Asks one input at a time. Use when the user invokes this
  skill, wants a new S3 bucket via that template, or says aws_s3_create /
  guided S3 module configuration.
disable-model-invocation: true
---

# aws_s3_create (skill id: `aws-s3-create`)

Skill path: **`skills/aws_s3_create/`** (from repository root). Entry router: **`.cursor/skills/ray-test/SKILL.md`**. Load **`skills/aws_s3_create/SKILL.md`** when the user asks for guided S3 creation or names **`aws_s3_create`** / **`aws-s3-create`**.

## Persona

You are a **senior AWS cloud DevOps engineer and architect**. Your role is to guide the user through **configuration and application** of a new AWS S3 bucket using the repository’s **template** module at **`infra/tf_lib/s3`**, materialized under **`infra/aws_tf/modules/`** and invoked from **`infra/aws_tf/main.tf`**, aligned with **current AWS S3 documentation** where the module is silent. **`terraform init` / `plan` / `apply` run only from `infra/aws_tf/`** (see **`.cursor/rules/infra.mdc`** and **`.cursor/rules/terrafrom.mdc`**).

> **Original role wording (verbatim from request):**  
> “you are a senio aws cloud devops and architetc, who role is to guide th euser inthe configuration and aplciation of a new aws s3 bucke”

## Non‑negotiables

1. **Owning service (`service`) before placement** — Must be exactly **`frontend`**, **`iam.service`**, or **`solutions.svc`** (**`frontend`** = Next.js app in **`aspire.svc/`**). Parse the **initial request and the full thread** for explicit slugs, **`infra/deployed/.../services/<slug>/`** paths, repo paths (`aspire.svc/`, `iam.service/`, `solutions.svc/`), or unambiguous wording per **[reference.md — Owning service](reference.md#owning-service-service)**. Also use **active workspace context** (e.g. the user’s open files or cwd under one of those service directories) when it **uniquely** implies an owner and the user did not name a different service. If **`service`** is already clear, **record it and do not ask** (a one-line acknowledgment is enough). If unclear, ask **one** short question listing the three slugs. **Never re-ask** for **`service`** once set unless the user corrects it.
2. **One parameter (or one clearly scoped field) per turn** — never ask for two unrelated inputs in the same message. Wait until the user’s answer is sufficient; then record it and move on.
3. **Read the module first** — open `infra/tf_lib/s3` (`variables_*.tf`, `locals.tf`, `checks.tf`, `outputs.tf`) so questions match real variable names, types, and validations.
4. **Defaults = private simple bucket** — all boolean feature flags default `false`; optional objects default `null`; see `locals.tf` header. Do not steer users toward public access or website hosting unless they explicitly need it.
5. **Cross‑dependencies** — enforce the same rules as `checks.tf` (e.g. replication / object lock / MFA delete require `versioning_enabled`; website requires `public_access_enabled`; CMK requires `kms_key_arn`; access logging target ≠ this bucket’s name).
6. **No Terraform apply from the agent** unless the user explicitly asks — you gather inputs, copy files, and edit HCL.

## Capabilities the module covers (summary)

| Area | What the module does |
|------|----------------------|
| Identity | `solution` object + `purpose` → deterministic global bucket name; extra `additional_tags`. |
| Privacy | `public_access_enabled` (default private); TLS-only bucket policy; `BucketOwnerEnforced` (no object ACLs). |
| Encryption | Default SSE-S3; optional SSE-KMS + bucket key via `customer_managed_key_enabled` + `kms_key_arn`. |
| Versioning / lock | `versioning_enabled`, `mfa_delete_enabled`, `object_lock_enabled`, `object_lock_default_retention`. |
| Lifecycle | Full `lifecycle_rules` passthrough; optional `abort_incomplete_multipart_upload_days`. |
| Replication | Single-destination `replication` object (requires versioning). |
| Observability / edges | `access_logging`, `eventbridge_enabled`, `inventory`, `transfer_acceleration_enabled`, `website`. |
| Operations | `force_destroy`, `default_storage_class` (documented intent, not a privacy toggle). |

For **per‑variable AWS semantics**, defaults, and “when to enable”, use **[reference.md](reference.md)** while questioning so guidance stays accurate without bloating this file.

## Workflow

### Phase A — owning service and placement (before parameter inventory)

**Arb Sherpa defaults (this repo):** unless the user overrides, the module copy lands under **`infra/aws_tf/modules/s3_<sanitized_purpose>/`** once **`purpose`** is known (see Phase B), and the **`module`** block is added to **`infra/aws_tf/main.tf`**. Run **`terraform`** only from **`infra/aws_tf/`**. The resolved **`service`** drives **`infra/deployed/.../services/<service>/terraform/aws/s3/`** (see **`.cursor/rules/infra.mdc`**).

**A0 — Owning service (`service`)**  
Resolve **`service`** ∈ {`frontend`, `iam.service`, `solutions.svc`} **before** asking placement questions, using **[reference.md — Owning service](reference.md#owning-service-service)**. If the user or thread already supplied it, **skip the question** and state the chosen slug once. If missing or ambiguous, ask **exactly one** question listing the three slugs. Track **`service`** in the running **`gathered`** map; **do not ask again** in later turns.

Ask **one question at a time** for anything still unknown, in this order:

1. **`service`** — only if not already resolved (see A0).
2. **Target directory** — only if the user wants a non-default path; otherwise after **`purpose`** is captured in Phase B, default to **`infra/aws_tf/modules/s3_<sanitized_purpose>/`** (snake_case, no duplicate slashes).
3. **Caller file** — where to add the `module` block (default: **`infra/aws_tf/main.tf`**).

Do **not** start the long parameter questionnaire until **`service`** is resolved and the **caller file** is known (or explicitly defaulted). The **target directory** may be finalized after **`purpose`** when using the **`s3_<sanitized_purpose>`** default.

### Phase B — record `solution` and `purpose` (still one field or small atomic step per message)

Use the **question order in [reference.md](reference.md#suggested-question-order-one-unit-per-message)**. For the `solution` object, each bullet is one message turn (e.g. first `solution.name`, then `solution.description`, …).

After each answer, maintain a **running `gathered` map** (in the reply) so the user can correct earlier values.

### Phase C — optional features (strictly one variable per message)

Follow **reference.md** sections **Dependencies** and **Suggested question order**. Skip questions for variables the user already said they want left at default (confirm once: “Leave all other module defaults as private/off?”).

### Phase D — materialize

When every required value is known:

1. **Copy** the directory **`infra/tf_lib/s3`** → the agreed **target directory** (filesystem copy: all `*.tf` plus `.terraform.lock.hcl`; omit `.terraform/`).
2. **Integrate** in the agreed caller file (usually **`infra/aws_tf/main.tf`**):
   - Add a `module` block with `source = "<relative path from that file to the copied module>"` (typically `"./modules/<folder>"` when **`main.tf`** lives in **`infra/aws_tf/`**).
   - Prefer **`solution = local.solution`** plus **`purpose`** and any non-default optional arguments (avoid duplicating the six `solution` fields unless the user explicitly needs different metadata).
   - Use a sensible module label (e.g. `module "s3_app_logs"`).
3. **Deployed map** — using the resolved **`service`** from Phase A, ensure **`infra/deployed/aws/<AWS_ACCOUNT_ID>/<AWS_DEFAULT_REGION>/services/<service>/terraform/aws/s3/`** exists; add **`.gitkeep`** if the folder is new. Use **`AWS_ACCOUNT_ID`** and **`AWS_DEFAULT_REGION`** from **`.cursor/rules/constants/constants.mdc`** (never guess another account or region).
4. Run **`terraform fmt`** on touched paths; run **`terraform validate`** from **`infra/aws_tf/`** when provider/backend allow.

### Phase E — handoff

Give a short checklist: **`cd infra/aws_tf`**, **`terraform init`**, **`terraform plan`**, confirm account/region (**`infra.mdc`** / **`constants.mdc`**), no secrets in **`.tfvars`**.

## Use cases (when this skill applies)

- New app or env needs an S3 bucket (logs, artifacts, uploads, static assets with clear trade‑offs).
- User wants **private by default** and optional advanced features explained.
- User points at **`infra/tf_lib/s3`** and wants help turning intent into HCL.

## Anti‑patterns

- Asking for multiple unrelated variables in one message.
- Enabling `website` or `public_access_enabled` without documenting public read implications.
- Skipping `checks.tf` constraints when suggesting values.
- Asking again which **`service`** owns the bucket after it was already stated or uniquely inferred.
- Copying the module before the user confirms destination and calling file.
- Running **`terraform`** from **`infra/deployed/`**, **`infra/tf_lib/`**, or any path other than **`infra/aws_tf/`** for this repo’s primary stack.

## Related repo rules

- **Account / region / profile**: `.cursor/rules/infra.mdc` and **`.cursor/rules/constants/constants.mdc`**
- **Terraform layout, `infra/deployed`, Helm map**: `.cursor/rules/terrafrom.mdc` and **`.cursor/rules/infra.mdc`**

---
name: aws-dynamodb-create
description: >-
  End-to-end guided creation of an AWS DynamoDB table: copy
  `infra/tf_lib/dynamodb` into `infra/aws_tf/modules/`, wire
  `infra/aws_tf/main.tf`, ownership markers under `infra/deployed/`, optional
  `terraform apply` using this repo’s AWS profile, post-apply validation with
  retry until clean, then a traffic-light summary and connection guidance. Use
  when the user wants DynamoDB via this template, names aws_dynamodb_create /
  aws-dynamodb-create, or asks to deploy / validate the table.
disable-model-invocation: false
---

# aws_dynamodb_create (skill id: `aws-dynamodb-create`)

Skill path: **`.cursor/skills/aws_dynamodb_create/`** (repository root). The same **`SKILL.md`** and **`reference.md`** are mirrored under **`iam.service/.cursor/skills/aws_dynamodb_create/`** and **`solutions.svc/.cursor/skills/aws_dynamodb_create/`** — load **`SKILL.md`** when the user asks for guided DynamoDB table creation, deployment, or validation, or names **`aws_dynamodb_create`** / **`aws-dynamodb-create`**.

## Persona

You are a **senior AWS cloud DevOps engineer and architect**. You guide the user through **discovery**, **Terraform materialization** (template → **`infra/aws_tf/modules/`** → **`infra/aws_tf/main.tf`**), optional **AWS deployment** using **`AWS_CLI_PROFILE`** and **`AWS_DEFAULT_REGION`** from **`.cursor/rules/constants.mdc`**, **post-apply validation**, and a concise **operational handoff** (what landed, where, how to connect). All **`terraform`** commands run **only** from **`infra/aws_tf/`** (see **`.cursor/rules/infra.mdc`** and **`.cursor/rules/terrafrom.mdc`**).

## Numbered multi-choice prompts (mandatory)

Whenever you ask the user to pick **exactly one** option from a **closed, finite** set anywhere in this skill (e.g. owning **`service`**, deploy yes/no, **`billing_mode`**, **`hash_key.type`** / **`range_key.type`** `S`/`N`/`B`, **`stream_view_type`**, **`table_class`**, GSI **`projection_type`**, confirm **`terraform.tfvars`** for `solution`, or any similar enum-like choice), you **must**:

1. **State the question** in a clear sentence (one topic only; do not combine unrelated picks).
2. **List every option** as a **numbered** markdown list: `1. …`, `2. …`, `3. …` (use `1.` / `2.` only for binary choices). Keep each line short; include the canonical value (slug, literal, or `true`/`false`) in the text.
3. **Tell the user how to reply:** e.g. “Reply with **1**, **2**, or **3** (the number only).” If they instead reply with text that **unambiguously** matches one option (e.g. the exact `service` slug), accept it and map it yourself.
4. **Map** the numeric reply to the canonical Terraform / `gathered` value; if the reply is missing, ambiguous, or out of range, **re-ask the same question** using the same numbered format.

**Free-text** inputs (e.g. **`purpose`**, attribute **names**, RCU/WCU numbers, **`kms_key_arn`**) do **not** use this pattern unless you are offering explicit presets—then still use numbers for those presets plus one option for “other (type below)”.

## Non‑negotiables

1. **Owning service (`service`) before placement** — Must be exactly **`frontend`**, **`iam.service`**, or **`solutions.svc`** (**`frontend`** = Next.js app in **`aspire.svc/`**). Resolve from thread, paths, or unique workspace context per **[reference.md — Owning service](reference.md#owning-service-service)**. If unclear, ask **one** question using **Numbered multi-choice** (three numbered options). **Never re-ask** once set unless the user corrects it.
2. **One atomic input per turn** — one variable, one GSI sub-step, or one **scoped** confirmation. For any **closed-set** pick, use **Numbered multi-choice**. Do not bundle **unrelated** questions in one message.
3. **Read the template before questioning** — open **`infra/tf_lib/dynamodb`** (`variables_*.tf`, `locals.tf`, `checks.tf`, `outputs.tf`, `dynamodb_table.tf`) so prompts match real variables and `check` rules.
4. **Defaults = minimal operational table** — on-demand billing by default; streams, TTL, PITR, CMK, deletion protection default **off/false** unless the user opts in.
5. **Respect `checks.tf`** — including **`gsi_include_requires_non_key_attributes`** (INCLUDE projections need non-empty `non_key_attributes`).
6. **Account / profile / region** — For every **AWS CLI** call, use **`AWS_CLI_PROFILE`** and **`AWS_DEFAULT_REGION`** from **`constants.mdc`** explicitly (`--profile`, `--region`). Run **pre-flight** `aws sts get-caller-identity` per **`infra.mdc`** before the first AWS or apply that touches the account. Do not deploy to another account or profile without explicit same-turn user override (rare).
7. **Terraform apply** — Run **`terraform apply`** (or **`apply -auto-approve`**) **only** after the user **explicitly** opts in to deploy in Phase F. If they decline, stop after validate/plan handoff.

## Capabilities (summary)

| Area | What the module does |
|------|----------------------|
| Identity | `solution` + `purpose` → deterministic table name; `additional_tags`. |
| Keys | Partition `hash_key`; optional sort `range_key` (`S` / `N` / `B`). |
| Capacity | `PAY_PER_REQUEST` (default) or `PROVISIONED` + RCU/WCU. |
| Indexes | Optional `global_secondary_indexes` (hash/range, projection, capacities when provisioned). |
| Encryption | Default AWS-owned; optional SSE-KMS via `customer_managed_encryption_enabled` + `kms_key_arn`. |
| Ops / durability | `point_in_time_recovery_enabled`, `deletion_protection_enabled`, `table_class`. |
| Streams / TTL | `stream_enabled` + `stream_view_type`; `ttl_enabled` + `ttl_attribute_name`. |

Per-variable semantics and question order: **[reference.md](reference.md)**.

## Workflow

### Phase A — owning service and placement

**Defaults (this repo):** module directory **`infra/aws_tf/modules/ddb_<sanitized_purpose>/`** after **`purpose`** is known; **`module`** block in **`infra/aws_tf/main.tf`**. **`service`** drives **`infra/deployed/aws/<AWS_ACCOUNT_ID>/<AWS_DEFAULT_REGION>/services/<service>/terraform/aws/dynamodb/`**.

**A0 — `service`** — Resolve per **[reference.md](reference.md#owning-service-service)**. Skip the question if already known.

Ask **one question at a time** for anything still unknown (topic order below uses bullets so it is not confused with user reply numbers **`1`/`2`/`3`**):

- **`service`** — only if not resolved (**Numbered multi-choice**: three options).
- **Target directory** — only if not default; else **`ddb_<sanitized_purpose>`** after **`purpose`**. If the user must pick between a small set of paths, use **Numbered multi-choice**; otherwise free-text the path.
- **Caller file** for the `module` block (default: **`infra/aws_tf/main.tf`**). If offering alternatives, use **Numbered multi-choice**; otherwise default without asking.

Do not start the full parameter questionnaire until **`service`** and the **caller file** are known (or defaulted).

### Phase B — `solution` and `purpose`

Follow **[reference.md — Suggested question order](reference.md#suggested-question-order-one-unit-per-message)**. If **`infra/aws_tf/terraform.tfvars`** already defines the six root solution inputs, you may ask **one** message: whether to use those values as-is for `solution = local.solution` — use **Numbered multi-choice** (e.g. `1.` Yes, use `terraform.tfvars` as-is · `2.` No, I will override fields). Keep a visible **`gathered`** map after each answer.

### Phase C — keys, billing, optional features

One variable (or one GSI field group) per message. Use **Numbered multi-choice** whenever the answer is a small fixed set (e.g. **`hash_key.type`** / **`range_key.type`**, **`billing_mode`**, **`projection_type`**, **`stream_view_type`**, **`table_class`**, boolean toggles). For **INCLUDE** projections, ensure `non_key_attributes` is non-empty (enforced in **`checks.tf`**).

### Phase D — materialize

1. **Copy** **`infra/tf_lib/dynamodb`** → target path (all `*.tf`, `.terraform.lock.hcl`; **never** copy `.terraform/`).
2. **Integrate** in the caller file: add `module "<label>" { source = "./modules/..." solution = local.solution purpose = "..." ... }` with required **`purpose`**, **`hash_key`**, and non-default optionals only. Use a **unique** module label (e.g. `ddb_orders`).
3. **Root outputs** — In **`infra/aws_tf/outputs.tf`**, add **alphabetically sorted** `output` blocks that re-expose the new module’s **`table_name`**, **`table_arn`**, **`region`**, and **`stream_arn`** / **`stream_label`** when streams are enabled (see **[reference.md — Root outputs](reference.md#root-outputs-pass-through)**).
4. **Deployed map** — Ensure **`infra/deployed/aws/<AWS_ACCOUNT_ID>/<AWS_DEFAULT_REGION>/services/<service>/terraform/aws/dynamodb/`** exists; add **`.gitkeep`** if new. Read account/region from **`constants.mdc`** only.
5. **`terraform fmt -recursive`** on touched paths under **`infra/aws_tf/`**; **`terraform validate`** from **`infra/aws_tf/`** (after **`terraform init`** if needed for providers).

### Phase E — plan handoff (always)

After a successful **`terraform validate`**:

- Show how to run **`cd infra/aws_tf`**, **`terraform init`**, **`terraform plan`**, and remind that the AWS provider profile for this stack is configured in **`infra/aws_tf/providers.tf`** (must stay aligned with **`AWS_CLI_PROFILE`** in **`constants.mdc`**).

### Phase F — optional deploy (user must opt in)

Ask **one** explicit question: **Do you want to deploy this DynamoDB table to AWS now?** Use **Numbered multi-choice**, e.g. `1.` Yes, deploy now · `2.` No, stop after plan/validate handoff.

- If **2** (no) — stop after Phase E; list files touched and next manual steps.
- If **1** (yes):
  1. **Pre-flight:** `aws sts get-caller-identity --profile "$AWS_CLI_PROFILE" --region "$AWS_DEFAULT_REGION" --output "$AWS_OUTPUT_FORMAT"` — verify **`Account`** equals **`AWS_ACCOUNT_ID`** from **`constants.mdc`** and exit code **0**; if not, **stop** and report (per **`infra.mdc`**).
  2. From **`infra/aws_tf/`**: **`terraform init`** (if not already), then **`terraform plan`**. On approval, **`terraform apply -auto-approve`** (or interactive apply if the user prefers — match their answer).

### Phase G — validate deployment and fix loop

Until validation passes or the user stops:

1. **`terraform output`** — Read the new root outputs (table name, ARN, region).
2. **AWS API:** `aws dynamodb describe-table --table-name "<table_name>" --profile "$AWS_CLI_PROFILE" --region "$AWS_DEFAULT_REGION"` — confirm **`TableStatus`** is **`ACTIVE`** (and **`LatestStreamArn`** if streams were enabled).
3. On **Terraform** failure: read stderr, fix **HCL** (module or root), run **`terraform fmt`**, **`terraform validate`**, **`terraform plan`**, then **`apply`** again.
4. On **AWS / state** errors: diagnose (naming, permissions, backend lock, wrong account), fix, retry from **`plan`**.
5. Cap **iterations** at a reasonable bound (e.g. **5** full fix/apply cycles); if still failing, summarize blockers and stop.

### Phase H — traffic-light summary and connection

Present a **markdown table** with status icons and plain-language labels (icons + text for accessibility):

- **🟢** = verified good (e.g. table ACTIVE, outputs present).
- **🟡** = present but not fully verified or optional feature off by design (e.g. streams disabled).
- **🔴** = failed / missing — should not appear if Phase G succeeded; if partial failure, explain.

Columns should include at least: **Check**, **Status**, **Where / value** (e.g. region, table name, ARN).

Then give **how to connect** (no secrets):

- **AWS CLI:** `aws dynamodb scan --table-name ... --profile ... --region ... --max-items 1` (illustrative).
- **SDK default:** standard DynamoDB endpoint for the region (`https://dynamodb.<region>.amazonaws.com` in public AWS; document **VPC endpoint** only if the user’s architecture uses one).
- **Stream consumers:** `stream_arn` from outputs when enabled.
- **IAM:** remind that workloads need **`dynamodb:*`** least-privilege on this table ARN; do not fabricate policy JSON unless the user asks.

## Anti‑patterns

- Multi-variable questionnaires in one message (except the single allowed **`solution`** batch confirmation against existing **`terraform.tfvars`**, which must still use **Numbered multi-choice**).
- Closed-set questions **without** a numbered option list or **without** telling the user to reply **`1`/`2`/`3`** (etc.).
- **`terraform apply`** without explicit user consent.
- Applying from **`infra/deployed/`** or **`infra/tf_lib/`**.
- Skipping **`aws sts`** pre-flight before deploy.
- Omitting **root `output`** passthroughs for a new table (operators cannot read module outputs without them).
- Guessing **`AWS_ACCOUNT_ID`** / region / profile instead of reading **`constants.mdc`**.

## Related repo rules

- **`.cursor/rules/infra.mdc`** — account, profile, region, **`infra/deployed`** map.
- **`.cursor/rules/constants.mdc`** — `AWS_ACCOUNT_ID`, `AWS_CLI_PROFILE`, `AWS_DEFAULT_REGION`.
- **`.cursor/rules/terrafrom.mdc`** — single root **`infra/aws_tf/`**, `local.solution`, sorted root outputs.
- **S3 sibling skill** — **`.cursor/skills/aws_s3_create/`**.

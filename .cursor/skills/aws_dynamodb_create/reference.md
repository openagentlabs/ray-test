# aws_dynamodb_create — module, deploy, and AWS reference

Terraform module template: **`infra/tf_lib/dynamodb`** (copy only; never `terraform init` in `tf_lib`).

## Arb Sherpa repository layout (mandatory)

| Path | Role |
|------|------|
| **`infra/tf_lib/dynamodb`** | Canonical template — **copy** into `infra/aws_tf/modules/`. |
| **`infra/aws_tf/modules/ddb_<sanitized_purpose>/`** | Default materialized module path after `purpose` is known. |
| **`infra/aws_tf/main.tf`** | Root composition: `module` blocks; prefer **`solution = local.solution`**. |
| **`infra/aws_tf/outputs.tf`** | Root outputs (alphabetically sorted); **re-expose** new module outputs (see below). |
| **`infra/aws_tf/`** | **Only** directory for **`terraform init` / `plan` / `apply`**. |
| **`infra/deployed/aws/<AWS_ACCOUNT_ID>/<AWS_DEFAULT_REGION>/services/<service>/terraform/aws/dynamodb/`** | Ownership markers (e.g. `.gitkeep`). Not a Terraform root. |

Use **`AWS_ACCOUNT_ID`** and **`AWS_DEFAULT_REGION`** from **`.cursor/rules/constants.mdc`** for deployed paths — never guess.

## Numbered multi-choice (mandatory for closed sets)

For any pick-one-from-a-list prompt (see skill **`SKILL.md`** — **Numbered multi-choice prompts**), use a numbered markdown list and instruct the user to reply with **`1`**, **`2`**, **`3`**, etc. Accept unambiguous text that matches one option.

### Example — owning `service` (when not already inferred)

> Which **owning service** should own this table in **`infra/deployed/.../services/<service>/`**?
>
> 1. **`frontend`** — Next.js app (**`aspire.svc/`**)
> 2. **`iam.service`** — IAM microservice
> 3. **`solutions.svc`** — ARB solutions service
>
> Reply with **1**, **2**, or **3** (number only), or the exact slug.

## Owning service (`service`) {#owning-service-service}

- **Allowed values:** **`frontend`**, **`iam.service`**, **`solutions.svc`** (exact folder names under `services/` in **`infra/deployed/.../`**).
- **Do not ask** if the user already gave a slug, a **`services/<slug>/`** path, repo path under **`aspire.svc/`**, **`iam.service/`**, or **`solutions.svc/`**, or unambiguous wording in the skill’s mapping table.
- **Do not ask** if active editor/cwd **uniquely** implies one service and the user did not contradict.
- **Never re-ask** after **`service`** is set unless the user changes scope.

| User wording (examples) | Map to `service` |
|-------------------------|------------------|
| `iam.service`, IAM microservice, **`iam.service/`** | `iam.service` |
| `solutions.svc`, ARB solutions, **`solutions.svc/`** | `solutions.svc` |
| `aspire.svc/`, Next.js app (deployed slug **`frontend`**) | `frontend` |

## Variables

| Variable | Default / shape | Capability |
|----------|-----------------|------------|
| `solution` | **required** object | `name`, `description`, `version`, `date`, `account_id`, `region`. |
| `purpose` | **required** string | Suffix for table name with `solution` + `account_id`. |
| `hash_key` | **required** `{ name, type }` | Partition key; `type` ∈ `S`, `N`, `B`. |
| `range_key` | `null` | Optional sort key; same shape. |
| `additional_tags` | `{}` | Extra resource tags. |
| `billing_mode` | `PAY_PER_REQUEST` | Or `PROVISIONED` (requires RCU/WCU). |
| `read_capacity` / `write_capacity` | `null` | Required when `PROVISIONED`. |
| `global_secondary_indexes` | `[]` | GSI list; see template `variables_indexes.tf`. |
| `customer_managed_encryption_enabled` | `false` | SSE-KMS when true + `kms_key_arn`. |
| `kms_key_arn` | `null` | CMK ARN when encryption flag true. |
| `point_in_time_recovery_enabled` | `false` | PITR. |
| `deletion_protection_enabled` | `false` | Blocks accidental delete when true. |
| `table_class` | `STANDARD` | Or `STANDARD_INFREQUENT_ACCESS`. |
| `stream_enabled` | `false` | DynamoDB Streams. |
| `stream_view_type` | `null` | Required when streams on. |
| `ttl_enabled` | `false` | TTL on table. |
| `ttl_attribute_name` | `null` | Required when TTL on. |

Attribute definitions are computed in `locals.tf` from keys and GSIs.

## Checks (mirror `checks.tf`)

- `PROVISIONED` ⇒ `read_capacity` and `write_capacity` set and `> 0`.
- `customer_managed_encryption_enabled` ⇒ non-empty `kms_key_arn`.
- `ttl_enabled` ⇒ non-empty `ttl_attribute_name`.
- `stream_enabled` ⇒ valid `stream_view_type`.
- GSI `projection_type = "INCLUDE"` ⇒ `non_key_attributes` non-empty (`gsi_include_requires_non_key_attributes`).
- Same attribute name cannot have conflicting types across table and GSIs.

## Suggested question order (one unit per message) {#suggested-question-order-one-unit-per-message}

If **`infra/aws_tf/terraform.tfvars`** already defines the root solution, use **one** message to confirm using it for `solution = local.solution` instead of asking field-by-field.

Otherwise, when **not** using root `local.solution` for every field, ask in order:

1. `solution.name` → 2. `solution.description` → 3. `solution.version` → 4. `solution.date` → 5. `solution.account_id` → 6. `solution.region`  
7. `purpose`  
8. `hash_key.name` → 9. `hash_key.type`  
10. Sort key? → if yes: `range_key.name`, `range_key.type`  
11. `billing_mode` → if `PROVISIONED`: `read_capacity`, then `write_capacity`  
12. `additional_tags` or “none”  
13. GSIs only if needed (per index: name, keys, projection, `non_key_attributes` for INCLUDE, capacities if provisioned)  
14. CMK toggle → `kms_key_arn` if true  
15. `point_in_time_recovery_enabled` → 16. `deletion_protection_enabled` → 17. `table_class`  
18. `stream_enabled` → `stream_view_type` if true  
19. `ttl_enabled` → `ttl_attribute_name` if true  

## Copy & `module` wiring

- Copy **`infra/tf_lib/dynamodb`** → **`infra/aws_tf/modules/ddb_<sanitized_purpose>/`** (or agreed path); include `.terraform.lock.hcl`; exclude `.terraform/`.
- `source` = relative from caller (typically `"./modules/ddb_<sanitized_purpose>"` from **`infra/aws_tf/main.tf`**).
- Pass **`solution = local.solution`** at repo root unless the user needs a custom object.

Minimal example:

```hcl
module "ddb_items" {
  source = "./modules/ddb_items"

  solution = local.solution
  purpose  = "items"

  hash_key = {
    name = "pk"
    type = "S"
  }
}
```

## Root outputs (pass-through) {#root-outputs-pass-through}

After adding a module **`module "ddb_items"`**, add **alphabetically sorted** root outputs in **`infra/aws_tf/outputs.tf`** so CI and operators can read values without `terraform console`:

```hcl
output "ddb_items_region" {
  description = "AWS region of the ddb_items DynamoDB table."
  value       = module.ddb_items.region
}

output "ddb_items_table_arn" {
  description = "ARN of the ddb_items DynamoDB table."
  value       = module.ddb_items.table_arn
}

output "ddb_items_table_name" {
  description = "Name of the ddb_items DynamoDB table."
  value       = module.ddb_items.table_name
}

# If streams enabled:
# output "ddb_items_stream_arn" { value = module.ddb_items.stream_arn }
```

Prefix outputs with the **module label** to avoid collisions. Match **`description`** style of existing root outputs.

## Deploy and validate (agent steps) {#deploy-and-validate}

**Constants:** read **`AWS_CLI_PROFILE`**, **`AWS_DEFAULT_REGION`**, **`AWS_ACCOUNT_ID`**, **`AWS_OUTPUT_FORMAT`** from **`.cursor/rules/constants.mdc`**.

**Pre-flight (mandatory before apply):**

```bash
aws sts get-caller-identity --profile "$AWS_CLI_PROFILE" --region "$AWS_DEFAULT_REGION" --output "$AWS_OUTPUT_FORMAT"
```

Proceed only if **`Account`** equals **`AWS_ACCOUNT_ID`** and exit code is **0** (**`infra.mdc`**).

**Terraform (from repo root):**

```bash
cd infra/aws_tf
terraform init
terraform plan
terraform apply -auto-approve   # only after explicit user consent for deploy
```

**Post-apply validation:**

```bash
terraform output -json   # or specific output names
aws dynamodb describe-table --table-name "<TABLE_NAME>" \
  --profile "$AWS_CLI_PROFILE" --region "$AWS_DEFAULT_REGION"
```

Expect **`TableStatus": "ACTIVE"`**. If streams were enabled, confirm **`LatestStreamArn`** in the describe response matches **`stream_arn`** output shape (same stream).

## Traffic-light summary (Phase H)

Example:

| Check | Status | Where / value |
|-------|--------|----------------|
| Terraform state updated | 🟢 OK | `infra/aws_tf` root |
| DynamoDB table ACTIVE | 🟢 OK | `table_name` = …, `region` = … |
| Streams | 🟡 N/A (off) | — |
| Root outputs defined | 🟢 OK | `outputs.tf` |

## Connection guidance (no secrets)

- **Regional endpoint (standard):** `https://dynamodb.<region>.amazonaws.com`
- **Table name:** from `terraform output` / `table_name` output.
- **CLI example:** `aws dynamodb describe-table --table-name <name> --profile <AWS_CLI_PROFILE> --region <AWS_DEFAULT_REGION>`
- **Application IAM:** grant least-privilege `dynamodb:GetItem`, `PutItem`, `Query`, etc., on **`table_arn`** (and **`stream_arn`** + `kinesis:Subscribe*` / Lambda event source mapping patterns if consuming streams).

## AWS documentation anchors

- [DynamoDB core concepts](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/HowItWorks.CoreComponents.html)  
- [Billing modes](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/HowItWorks.ReadWriteCapacityMode.html)  
- [Secondary indexes](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/SecondaryIndexes.html)  
- [Encryption at rest](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/encryption.html)  
- [Point-in-time recovery](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/PointInTimeRecovery.html)  
- [DynamoDB Streams](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/Streams.html)  
- [TTL](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/TTL.html)  
- [Table classes](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/HowItWorks.TableClasses.html)

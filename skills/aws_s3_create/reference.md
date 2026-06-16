# aws_s3_create — module & AWS reference

Canonical Terraform source: **`infra/tf_lib/s3`** (25 `.tf` files: bucket, policy, encryption, versioning, lifecycle, replication, logging, inventory, website, checks, `versions.tf`, variables split by domain, etc.).

## Arb Sherpa repository layout (mandatory for this repo)

- **Template (read-only):** **`infra/tf_lib/s3`** — copy from here; never run `terraform` in this directory.
- **Materialized module:** **`infra/aws_tf/modules/s3_<sanitized_purpose>/`** by default once **`purpose`** is known (override if the user requests another path).
- **Root composition:** **`infra/aws_tf/main.tf`** — add the `module` block here; prefer **`solution = local.solution`** (see **`.cursor/rules/terrafrom.mdc`**).
- **Terraform CLI:** run **`terraform init`**, **`plan`**, **`validate`** only from **`infra/aws_tf/`** (see **`.cursor/rules/infra.mdc`**).
- **Ownership map:** after adding a bucket for a resolved **`service`** (`frontend`, `iam.service`, or `solutions.svc`), keep **`infra/deployed/aws/<AWS_ACCOUNT_ID>/<AWS_DEFAULT_REGION>/services/<service>/terraform/aws/s3/`** in sync (add **`.gitkeep`** if the path is new). IDs and region: **`.cursor/rules/constants/constants.mdc`**. See **[Owning service](reference.md#owning-service-service)**.

## Owning service (`service`) {#owning-service-service}

- **Allowed values** (exact folder names under `services/` in **`infra/deployed/.../`**): **`frontend`**, **`iam.service`**, **`solutions.svc`**. The Next.js app’s **source** lives in **`aspire.svc/`** on disk; when **`service`** is **`frontend`**, ownership markers go under **`.../services/frontend/`**.
- **Do not ask** the user which service applies if any of the following is already true in the **current turn or earlier thread**:
  - They named a slug literally (e.g. “for **iam.service**”, “under **solutions.svc**”).
  - They gave a repo or deployed path containing `services/<one-of-the-slugs>/`.
  - They pointed at a directory such as **`aspire.svc/`**, **`iam.service/`**, or **`solutions.svc/`** as the owning codebase for this bucket.
- The agent’s **active context** (e.g. open file or cwd under **`iam.service/`**, **`solutions.svc/`**, or **`aspire.svc/`**) uniquely implies that service **and** the user did not scope a different owner — then use that slug **without asking**.
- **Infer only when confident** using the table below; if two services could fit, ask **one** clarifying question listing the three slugs.
- **Never re-ask** for **`service`** after it has been set unless the user explicitly changes scope.

| User wording (examples) | Map to `service` |
|---------------------------|------------------|
| `iam.service`, IAM microservice, identity service in **`iam.service/`** | `iam.service` |
| `solutions.svc`, ARB solutions service, **`solutions.svc/`** | `solutions.svc` |
| `aspire.svc/`, Next.js app (deployed **`service`** slug **`frontend`**) web UI | `frontend` |

**Deployed marker directory (S3):**  
`infra/deployed/aws/<AWS_ACCOUNT_ID>/<AWS_DEFAULT_REGION>/services/<service>/terraform/aws/s3/`  
(Read **`AWS_ACCOUNT_ID`** and **`AWS_DEFAULT_REGION`** from **`.cursor/rules/constants/constants.mdc`**.)

## Variables (module contract)

| Variable | Type / shape | Default | Capability & typical use |
|----------|----------------|---------|---------------------------|
| `solution` | object | **required** | `name`, `description`, `version`, `date`, `account_id`, `region` — propagated into naming/tags posture; must match org rules (`infra.mdc`). |
| `purpose` | string | **required** | Short slug for bucket suffix; part of global name. |
| `additional_tags` | map(string) | `{}` | Extra resource tags beyond provider `default_tags`. |
| `default_storage_class` | string | `STANDARD` | **Intent only** (documented); objects still use class on PUT / lifecycle. Values: STANDARD, INTELLIGENT_TIERING, STANDARD_IA, ONEZONE_IA, GLACIER_IR, GLACIER, DEEP_ARCHIVE. |
| `public_access_enabled` | bool | `false` | **Single switch** for all four `PublicAccessBlock` settings. `false` = block public ACLs/policies (private to anonymous internet). |
| `force_destroy` | bool | `false` | Allow empty bucket delete on destroy; keep `false` for prod data. |
| `customer_managed_key_enabled` | bool | `false` | `false` = SSE‑S3 (AES256); `true` = SSE‑KMS + S3 bucket key. |
| `kms_key_arn` | string | `null` | Required if CMK enabled; key policy must allow S3/use in this account/region. |
| `versioning_enabled` | bool | `false` | Keep multiple versions; needed for replication, object lock, MFA delete request. |
| `mfa_delete_enabled` | bool | `false` | Requests MFA delete on versioning; **root MFA still required** to actually enable in AWS. |
| `object_lock_enabled` | bool | `false` | WORM at **bucket create** only; requires versioning. |
| `object_lock_default_retention` | object or null | `null` | `{ mode = GOVERNANCE \| COMPLIANCE, days = N }`; omit if no default retention. |
| `abort_incomplete_multipart_upload_days` | number or null | `null` | e.g. `7` — abort stale MPU parts (cost hygiene). |
| `lifecycle_rules` | list(object) | `[]` | Full provider passthrough: transitions, expiration, noncurrent rules, filters. |
| `replication` | object or null | `null` | Single destination: dest ARN, IAM role ARN, optional prefix, storage class, delete markers, dest KMS ARN. **Requires versioning.** |
| `access_logging` | object or null | `null` | `{ target_bucket, target_prefix }`; target must **not** be this bucket (infinite loop). |
| `eventbridge_enabled` | bool | `false` | Send bucket events to default EventBridge bus. |
| `inventory` | object or null | `null` | Periodic inventory to another bucket (CSV/ORC/Parquet). |
| `transfer_acceleration_enabled` | bool | `false` | Edge network acceleration; extra cost. |
| `website` | object or null | `null` | Static site or redirect; **requires** `public_access_enabled = true` + public read policy path. Prefer CloudFront+OAC for prod web. |

## Dependencies (mirror `checks.tf`)

- `customer_managed_key_enabled` ⇒ must set `kms_key_arn`.
- `mfa_delete_enabled` ⇒ `versioning_enabled = true`.
- `object_lock_enabled` ⇒ `versioning_enabled = true`.
- `replication != null` ⇒ `versioning_enabled = true`.
- `website != null` ⇒ `public_access_enabled = true`.
- `access_logging` ⇒ `target_bucket` ≠ this module’s computed bucket name.

## Suggested question order (one unit per message)

When the **`module`** block uses **`solution = local.solution`** in **`infra/aws_tf/main.tf`**, confirm once that root **`terraform.tfvars`** matches the user’s intent instead of asking for each `solution.*` field individually.

Ask in this sequence; skip any variable the user wants at **module default** (confirm once globally).

1. `solution.name`
2. `solution.description`
3. `solution.version` (semver)
4. `solution.date` (ISO date)
5. `solution.account_id` (confirm matches `infra.mdc` unless user overrides in turn)
6. `solution.region` (confirm `us-east-1` / policy unless override)
7. `purpose`
8. `additional_tags` (map or “none”)
9. `default_storage_class` (or accept STANDARD)
10. `public_access_enabled` (default false — confirm)
11. `force_destroy` (default false — confirm)
12. `customer_managed_key_enabled` → if true, then **next message** `kms_key_arn`
13. `versioning_enabled`
14. `mfa_delete_enabled` (only if versioning true; explain root MFA caveat)
15. `object_lock_enabled` → if true, versioning must be true; then `object_lock_default_retention` in separate messages (`mode`, then `days`, or null)
16. `abort_incomplete_multipart_upload_days` (or null)
17. `lifecycle_rules` (complex — ask if they need transitions/expiry; if yes, collect one rule at a time or accept “defer to later PR”)
18. `replication` (only if cross-bucket copy needed; collect subfields one at a time: dest ARN, role ARN, prefix, …)
19. `access_logging` (target bucket + prefix)
20. `eventbridge_enabled`
21. `inventory` (only if compliance/ops needs manifest)
22. `transfer_acceleration_enabled`
23. `website` (only if static hosting on S3 is accepted; warn public read)

## AWS documentation anchors (agent should consult when ambiguous)

Use current AWS docs for behaviour not duplicated in the module, especially:

- [S3 User Guide — Bucket policies](https://docs.aws.amazon.com/AmazonS3/latest/userguide/bucket-policies.html)
- [Blocking public access](https://docs.aws.amazon.com/AmazonS3/latest/userguide/access-control-block-public-access.html)
- [Encryption](https://docs.aws.amazon.com/AmazonS3/latest/userguide/UsingEncryption.html)
- [Versioning](https://docs.aws.amazon.com/AmazonS3/latest/userguide/Versioning.html)
- [Replication](https://docs.aws.amazon.com/AmazonS3/latest/userguide/replication.html)
- [Lifecycle](https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-lifecycle-mgmt.html)
- [Object Lock](https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-lock.html)
- [Website hosting](https://docs.aws.amazon.com/AmazonS3/latest/userguide/WebsiteHosting.html)
- [Inventory](https://docs.aws.amazon.com/AmazonS3/latest/userguide/storage-inventory.html)
- [EventBridge](https://docs.aws.amazon.com/AmazonS3/latest/userguide/EventBridge.html)

## Copy & `module` wiring

- **Copy**: entire **`infra/tf_lib/s3`** tree → **`infra/aws_tf/modules/s3_<sanitized_purpose>/`** (or user-agreed path); include `.terraform.lock.hcl`; exclude `.terraform/`.
- **`source`**: relative path from the file containing the `module` block to the copied directory (from **`infra/aws_tf/main.tf`**, typically `"./modules/<name>"`).
- **Root wiring**: pass **`solution = local.solution`** unless the user explicitly needs a custom `solution` object.
- **Minimal call example** at the repo root (`infra/aws_tf/main.tf`):

```hcl
module "s3_example" {
  source = "./modules/s3_example"

  solution = local.solution
  purpose  = "app_logs"
}
```

Add optional arguments only where the user deviated from defaults.

When **`module`** lives outside the root (not recommended in this repo), use an explicit `solution = { ... }` object aligned with **`terraform.tfvars`** / **`constants.mdc`**.

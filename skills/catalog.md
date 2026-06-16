# Ray Test skills catalog

Canonical skill bodies live under **`skills/<id>/`**. The entry router is **`.cursor/skills/ray-test/SKILL.md`**.

Agents: read this table when routing; then open **`skills/<id>/SKILL.md`** and follow that skill end-to-end.

| # | ID | Folder | Triggers (examples) | Summary |
|---|-----|--------|---------------------|---------|
| 1 | `tf` | `skills/tf/` | `tf`, `terraform`, plan, apply, fmt, validate, registry module search | Terraform CLI from `infra/aws/aws_tf/` plus **tf-tool** registry CLI |
| 2 | `prj` | `skills/prj/` | `prj`, `prj init`, `PRJ_NAME`, project constants | Interactive init/show for Group 1 **`PRJ_*`** in `constants.mdc` |
| 3 | `aws-dynamodb-create` | `skills/aws_dynamodb_create/` | `aws_dynamodb_create`, DynamoDB table, deploy table | Guided DynamoDB module copy, wire, optional apply, validate |
| 4 | `aws-s3-create` | `skills/aws_s3_create/` | `aws_s3_create`, S3 bucket, deploy bucket | Guided S3 module copy, wire, optional apply, validate |
| 5 | `rules-create` | `skills/rules-create/` | `rules-create`, new Cursor rule, `.mdc` scaffold | Interactive new rule file from `rules/template.mdc` |

## Component-scoped skills (not in this catalog)

These stay under their service tree; the router may point to them but does not own their workflow:

| ID | Path |
|----|------|
| `page-create` | `aspire.svc/.cursor/skills/page-create/` |
| `aspire-registry-tool` | `aspire.svc/.cursor/skills/aspire-registry-tool/` |

## Shared reference

| File | Purpose |
|------|---------|
| `skills/_shared/workflow-reference.md` | Generic **`WorkflowStart:`** / **`Jmp:`** / **`Delay:`** DSL for repo skills |

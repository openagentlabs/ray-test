# Dev environment — `router.svc` AWS resources

Provisions ECR repositories and IRSA for the routing-tier on an **existing** EKS cluster.
Routing-tier state lives in the **shared backend Postgres** (RDS) — there are no
DynamoDB tables. The dedicated `pod_manager` schema and its `pm_*` tables are created
automatically by `router.svc` at startup (`CREATE SCHEMA IF NOT EXISTS` +
`CREATE TABLE IF NOT EXISTS`).

## Quick start (ECR + IAM)

```bash
cd infra/terraform/environments/dev
cp terraform.tfvars.example terraform.tfvars
# Edit: eks_cluster_name (required), aws_region, service_name, db_table_prefix

terraform init
terraform plan
terraform apply
```

## Database connectivity

`router.svc` reads `DATABASE_URL` for the shared Postgres. Provide it one of two ways:

- **Kubernetes Secret (default):** create a secret in the routing namespace and
  reference it from Helm (`podManager.databaseUrlSecret`). Leave
  `database_url_secret_arn` empty.
- **Secrets Manager:** set `database_url_secret_arn` so the IRSA role can read it.

`db_table_prefix` here must match `router.svc/server/app_config.toml`
`[postgres].table_prefix` and Helm `podManager.postgres.tablePrefix`.

## Outputs

```bash
terraform output db_table_prefix
terraform output pod_manager_irsa_role_arn
terraform output -raw helm_set_flags
```

Wire IRSA and the table prefix into Helm (`infra/helm/routing-tier`).

## Connectivity note (architecture)

The backend's Postgres lives in the MIDAS VPC `vpc-0c4d673f3e95a93eb`. To reach it,
deploy `pod_manager` into that VPC (set `create_vpc = false` and supply
`existing_vpc_id` / `existing_private_subnet_ids`) and allow the routing-tier
security group inbound to the RDS security group on 5432. See
`docs/adr/0001-pod-manager-shared-postgres.md`.

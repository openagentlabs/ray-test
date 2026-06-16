# Redeploy after `terraform destroy`

Remote state in S3 (`arb-ai-assistant-terraform-state`) is **not** destroyed by `terraform destroy` in this root.

## Prerequisites (keep on your machine)

- `iam.svc/server/.env.local`, `solutions.svc/server/.env.local`, `storage.svc/server/.env.local`, `notification.svc/server/.env.local`, `general.ai.agent.svc/server/.env.local`
- `frontend/.env.local` and/or `infra/containers/compose/.env.local` (for `AUTH_SECRET` and IAM bootstrap)
- AWS CLI profile `kt-acc` (see `.cursor/rules/constants/constants.mdc`)
- Docker, `kubectl`, and `helm` (for image build/push and EKS rollout)

## Full restore

From the repository root:

```bash
python3 make/scaffold_secrets.py dev
make build-dev
# or: python3 make/build.py dev --yes
```

This runs: `validate_secrets` → `terraform apply` (var-files under `infra/envs/dev/`) → `build` → `ecr` push → `helm` rollout → `aws` / `validate_curl`.

Skip image build: `python3 make/build.py dev --yes --skip-build`. Post-Terraform only: `python3 infra/containers/scripts/post_deploy.py dev`.

`infra/envs/dev/terraform.tfvars` should keep `containers_eks_enabled = true`.

After apply, open CloudWatch → **Dashboards** → output `eks_cloudwatch_dashboard_name` (default `arb_ai_assistant-eks-arb-ai-assistant`) for pod metrics and log widgets.

## Data note

Destroy removes **DynamoDB tables** and the **S3** general bucket managed by Terraform. Redeploy recreates empty tables; IAM bootstrap env vars re-seed the admin user when tables are empty.

## Migrating from ECS

If this account previously ran the ECS stack, `terraform apply` will destroy ECS resources and create EKS. Plan carefully before applying in shared environments.

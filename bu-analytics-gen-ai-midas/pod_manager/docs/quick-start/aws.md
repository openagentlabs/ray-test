# AWS quick start

Deploy to the dev EKS stack after Terraform provisioning. Endpoint variables for CLI and clients are in [`config/deploy/aws.env`](../../config/deploy/aws.env) (generated after deploy).

**Prerequisites:** AWS CLI, Terraform ≥ 1.5, Helm 3, kubectl, Docker. Copy [`infra/terraform/environments/dev/terraform.tfvars.example`](../../infra/terraform/environments/dev/terraform.tfvars.example) to `terraform.tfvars` before apply.

## 1. Provision platform

EKS, ECR, IRSA, ALB controller. Routing state lives in the shared backend Postgres
(no DynamoDB); provide its `DATABASE_URL` via a Kubernetes Secret or Secrets Manager
(see [ADR 0004](../../../docs/adr/0004-pod-manager-shared-postgres.md)).

| Step | Run |
|------|-----|
| `make init` | [▶ Run](command:workbench.action.tasks.runTask?%5B%22qs-aws-tf-init%22%5D) |
| `make validate-all` | [▶ Run](command:workbench.action.tasks.runTask?%5B%22qs-aws-tf-validate%22%5D) |
| `make plan-dev` | [▶ Run](command:workbench.action.tasks.runTask?%5B%22qs-aws-tf-plan%22%5D) |
| `make apply-dev` | [▶ Run](command:workbench.action.tasks.runTask?%5B%22qs-aws-tf-apply%22%5D) |

```bash
cd infra/terraform
make init
make validate-all
make plan-dev
make apply-dev
```

## 2. Configure kubectl

Cluster name from Terraform output, e.g. `dev-pod-manager` — [▶ Run](command:workbench.action.tasks.runTask?%5B%22qs-aws-kubeconfig%22%5D)

```bash
aws eks update-kubeconfig --region us-east-1 --name dev-pod-manager
```

## 3. Build, push, and deploy workloads

| Step | Run |
|------|-----|
| Build and push images | [▶ Run](command:workbench.action.tasks.runTask?%5B%22qs-aws-build-push%22%5D) |
| Helm deploy | [▶ Run](command:workbench.action.tasks.runTask?%5B%22qs-aws-helm-deploy%22%5D) |

```bash
./infra/scripts/build-push-images.sh
./infra/scripts/deploy-helm.sh
```

## 4. Write client/CLI endpoints

[▶ Run](command:workbench.action.tasks.runTask?%5B%22qs-aws-write-profile%22%5D)

Regenerates `config/deploy/aws.env` from live load balancers and prints confirmation in the terminal.

```bash
./infra/scripts/write-aws-profile.sh
source config/deploy/aws.env
```

## 5. Verify

[▶ Run](command:workbench.action.tasks.runTask?%5B%22qs-aws-dev-test%22%5D)

```bash
source config/deploy/aws.env
cd dev_testing && uv sync
uv run dev-test all --target aws
```

## Next steps

- Full runbook [../../infra/README.md](../../infra/README.md)
- Env reference [../DEPLOYMENT_PARAMETERS.md](../DEPLOYMENT_PARAMETERS.md)
- Ports and URLs [../ENDPOINTS.md](../ENDPOINTS.md)

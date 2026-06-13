# Infrastructure — AWS (Terraform) + EKS (Helm)

Deploys **VPC**, **EKS**, **ECR**, **IRSA**, **AWS Load Balancer Controller**, and the full **routing-tier** workload on AWS. Routing state lives in the shared backend Postgres (RDS), which this stack does not provision. Local development uses Docker Compose unchanged.

## Prerequisites

- AWS CLI configured
- [Terraform](https://www.terraform.io/) >= 1.5
- [Helm](https://helm.sh/) 3.x
- [kubectl](https://kubernetes.io/docs/tasks/tools/)
- Docker (build/push images)

## Layout

```
config/deploy/           # local.env and aws.env endpoint profiles
infra/
  docker/                # Local Compose stack (unchanged)
  scripts/
    build-push-images.sh
    deploy-helm.sh
    write-aws-profile.sh
  terraform/
    modules/
      vpc/               # VPC + single NAT
      eks/               # EKS managed node group
      eks-alb-controller/
      ecr-repositories/
      iam-pod-manager/
    environments/dev/
  helm/routing-tier/     # Envoy + router.svc + backend pool + login pod
dev_testing/             # uv test runner (local + aws)
```

## 1. Terraform validate and apply

```bash
cd infra/terraform
make init
make validate-all
make plan-dev
make apply-dev
```

Configure `environments/dev/terraform.tfvars` from [`terraform.tfvars.example`](terraform/environments/dev/terraform.tfvars.example).

Key outputs: `ecr_repository_urls`, `pod_manager_irsa_role_arn`, `helm_set_flags`, `cluster_name`, `kubeconfig_command`.

## 2. Configure kubectl

```bash
aws eks update-kubeconfig --region us-east-1 --name dev-pod-manager
```

## 3. Build and push images

```bash
./infra/scripts/build-push-images.sh
```

## 4. Helm deploy

```bash
./infra/scripts/deploy-helm.sh
```

Uses [`values.yaml`](helm/routing-tier/values.yaml) + [`values-aws.yaml`](helm/routing-tier/values-aws.yaml):
- **HTTP :80** enabled (default)
- **HTTPS :443** disabled until `ingress.listeners.https.certificateArn` is set

## 5. Write AWS client profile

```bash
./infra/scripts/write-aws-profile.sh
source config/deploy/aws.env
```

## 6. Test

```bash
cd dev_testing && uv sync
uv run dev-test all --target aws
```

Local stack (unchanged):

```bash
./infra/docker/start-local.sh -r -s -d
uv run dev-test all --target local
```

## Workloads deployed

| Workload | Replicas | Notes |
|----------|----------|-------|
| routing-tier (Envoy + router.svc) | 3 | ALB → :10000; NLB → gRPC :8804 |
| backend-pool-node | 3 | StatefulSet, headless Service |
| login-pod | 2 | ClusterIP Service |

## Documentation

- [docs/DEPLOYMENT_PARAMETERS.md](../docs/DEPLOYMENT_PARAMETERS.md) — all env vars and sources
- [docs/ENDPOINTS.md](../docs/ENDPOINTS.md) — ports and URLs
- [docs/README.md](../docs/README.md) — docs index
- [docs/quick-start/local.md](../docs/quick-start/local.md) — local quick start

## Cost notes (dev)

Single NAT gateway, 2× `t3.medium` nodes, ECR lifecycle (30 images). See plan cost table in repo docs.

# ARB container images and local compose

Docker build definitions, local orchestration, and pointers to AWS ECR/EKS Terraform
under `infra/aws_tf/`.

## Layout

| Path | Purpose |
|------|---------|
| `../../iam.svc/server/Dockerfile` (and siblings) | **Canonical** Python gRPC image per service |
| `../../frontend/Dockerfile` | **Canonical** Next.js frontend image |
| `images/python-grpc-service/Dockerfile` | Deprecated shared template |
| `images/frontend/Dockerfile` | Deprecated copy of frontend Dockerfile |
| `compose/docker-compose.yml` | Local six-service stack |
| `scripts/rebuild_all.py` | Build all images (and optionally `compose up` / `down`) |
| `scripts/deploy_to_aws.py` | Thin wrapper → `make/build.py dev` |
| `../../make/build.py` | Unified entry: `local` / `dev` / `test` / `prod` (see repo `Makefile`) |
| `scripts/deploy_lib.py` | Shared phases (Terraform var-files, ECR, Helm/EKS, validation) |
| `scripts/post_deploy.py` | Post-Terraform only (build → ECR → Helm → curl) |

Ownership markers for AWS primitives live under
`infra/deployed/aws/<account>/<region>/services/<service>/terraform/aws/{ecr,eks}/`.

Runnable Terraform (EKS Fargate + ECR + IRSA) is composed from
`infra/aws_tf/modules/workloads_infra/` and `infra/aws_tf/modules/containers_stack/`
when `containers_eks_enabled = true` in `infra/aws_tf/terraform.tfvars`.

Helm chart: `infra/deployed/aws/017868795096/us-east-1/helm/workload/` (shared by all services).

## EKS CloudWatch observability

When `containers_eks_enabled = true`, Terraform also provisions:

| Component | Purpose |
|-----------|---------|
| **`amazon-cloudwatch-observability` EKS addon** | Container Insights (pod CPU/memory/network, restarts) via IRSA |
| **Control plane logs** | `/aws/eks/<cluster>/cluster` (api, audit, authenticator, controllerManager, scheduler) |
| **Fargate container logs** | `/arb/<solution>/eks/<cluster>/containers` + per-service routing into `/arb/<solution>/services/*` |
| **Container Insights logs** | `/aws/containerinsights/<cluster>/application` (and performance/dataplane groups) |
| **CloudWatch dashboard** | `arb_ai_assistant-eks-arb-ai-assistant` — metrics + Logs Insights widgets |

Open the dashboard in AWS Console → CloudWatch → Dashboards, or use terraform output `eks_cloudwatch_dashboard_name`.

Application structured logs (OpenTelemetry / SDK) continue to use the existing per-service log groups from `cloudwatch_application_logs`; Fargate stdout/stderr is additionally captured by Fluent Bit.

## Services and ports

| Service | Compose name | Port | AWS ECR repo (when EKS enabled) |
|---------|--------------|------|----------------------------------|
| IAM | `iam` | 8803 | `arb-ai-assistant-iam-svc` |
| Solutions | `solutions` | 8804 | `arb-ai-assistant-solutions-svc` |
| Storage | `storage` | 8805 | `arb-ai-assistant-storage-svc` |
| General AI agent | `general-ai-agent` | 8806 | `arb-ai-assistant-general-ai-agent-svc` |
| Notification | `notification` | 8807 | `arb-ai-assistant-notification-svc` |
| Frontend | `frontend` | 8802 | `arb-ai-assistant-frontend` |

## Local prerequisites

1. Docker Engine with Compose v2.
2. Per-service AWS credentials in `*/server/.env.local` (copy from `*/server/.env.example`).
3. Optional: `infra/containers/compose/.env.local` from `compose/.env.local.example` for `AUTH_SECRET` and IAM bootstrap values.

## Fast local dev (bare metal, no Docker)

From the **repository root** (returns in ~1s; processes warm up in background):

```bash
make start-local  # IAM, solutions, storage, general AI agent, notification, frontend (8802)
make stop-local
```

Requires Python venvs per `*/server/README.md` and `npm install` in `frontend/`. Uses `infra/envs/dev/local.env` for loopback gRPC hosts.

## Build images

From the **repository root**:

```bash
# Compile gRPC clients + build every Docker image (recommended)
make build-dockers

# Docker only (skip client compile)
python3 make/build_docker.py --skip-compile

# Legacy wrapper (docker build only)
python3 infra/containers/scripts/rebuild_all.py
```

## Build and run (Compose)

From the **repository root**:

```bash
# Build every image (docker only; no client compile)
python3 infra/containers/scripts/rebuild_all.py

# Build and start detached
python3 infra/containers/scripts/rebuild_all.py --up

# Stop the stack
python3 infra/containers/scripts/rebuild_all.py --down

# Rebuild one service
python3 infra/containers/scripts/rebuild_all.py --service iam --up
```

Open the UI at http://127.0.0.1:8802. Compose uses `APP_ENV=dev` + `APP_TARGET=local` and
`infra/envs/dev/compose.env` for gRPC hostnames (`iam`, `storage`, …).

## Frontend configuration (`APP_ENV` + `APP_TARGET`)

| Target | `APP_TARGET` | gRPC hosts (default) |
|--------|--------------|----------------------|
| bare metal (`make start-local`) | `local` | `127.0.0.1` (see `infra/envs/dev/local.env`) |
| Docker Compose | `local` + `compose.env` | Compose service names |
| EKS Fargate | `aws` | `<service>.arb-ai-assistant.svc.cluster.local` (in `infra/envs/<env>/k8s.tfvars`) |

Override endpoints in `frontend/.env.local` (see `frontend/.env.example`).

## AWS: ECR + EKS Fargate (automated)

From the **repository root**:

```bash
make build-dev          # or: python3 make/build.py dev --yes
make build-local        # compose validate
```

Per-environment committed config: `infra/envs/{dev,test,prod}/terraform.tfvars`, `k8s.tfvars`.
Secrets (gitignored): `python3 make/scaffold_secrets.py dev` → `infra/envs/<env>/secrets.auto.tfvars`.
Deploy scripts do **not** mutate committed tfvars at runtime.

### Manual steps (equivalent)

1. Enable in `infra/aws_tf/terraform.tfvars`:

   ```hcl
   containers_eks_enabled = true
   containers_image_tag   = "latest"
   ```

2. Plan/apply from `infra/aws_tf/` (see `.cursor/rules/infra.mdc` for account binding).

3. Push images and deploy with Helm (after `terraform apply`):

   ```bash
   make start-aws ARGS="--yes"
   ```

4. Note outputs:
   - `containers_eks_cluster_name` — EKS cluster
   - `containers_k8s_service_dns_names` — in-cluster gRPC hostnames
   - Frontend public URL from the `frontend` Service LoadBalancer (via `kubectl get svc frontend`)

ECR repositories use **lifecycle policies** (expire untagged after 1 day, keep the last 10 tagged images) for lower storage cost.

## Dependencies (summary)

| Service | AWS / data dependencies |
|---------|---------------------------|
| **iam.svc** | DynamoDB (IAM tables) |
| **solutions.svc** | DynamoDB (solutions + history) |
| **storage.svc** | SQLite volume (Compose) / ephemeral path (EKS), S3 `exlservice-arb-general` |
| **notification.svc** | SNS notifications topic |
| **collaboration.svc** | DynamoDB (aliases + discussions) |
| **document-storage.svc** | DynamoDB registry/groups + runtime group tables, S3 docstore attachments, OpenSearch Serverless vector search, Bedrock Titan embeddings (IRSA) |
| **general.ai.agent.svc** | Amazon Bedrock (IRSA on EKS) |
| **arch.diagram.agent.svc** | Amazon Bedrock + DynamoDB conversion jobs (IRSA); gRPC to **document-storage.svc** (RKS) and **storage.svc** (images) |
| **frontend** | gRPC to backends including document-storage and arch-diagram-agent |

**arch.diagram.agent.svc** is the only Python service that calls other gRPC services outbound; **frontend** is the primary user-facing consumer.

# MIDAS Deployment Journal

Everything we did to take the MIDAS application from a partially-wired codebase to a fully deployment-ready state - covering local Docker, Jenkins CI, and AWS EKS (Helm).

---

## Table of Contents

1. [Starting Point - What Was Already There](#1-starting-point)
2. [Branch Setup](#2-branch-setup)
3. [Docker Images - Replacing Stub Nginx with Real Services](#3-docker-images)
4. [Local Development Setup](#4-local-development-setup)
5. [AWS Services - What We Use and Where](#5-aws-services)
6. [Secrets Management Strategy](#6-secrets-management-strategy)
7. [Jenkins Pipeline - What We Added and Why](#7-jenkins-pipeline)
8. [Helm / EKS Deployment](#8-helm--eks-deployment)
9. [Mistakes Made and How We Fixed Them](#9-mistakes-made-and-how-we-fixed-them)
10. [Quick Reference - How to Run Everything](#10-quick-reference)

---

## 1. Starting Point

The repository had:
- A working **backend** (FastAPI/Python) with a `Dockerfile`
- A working **frontend** (Node.js/React) with a `Dockerfile`
- A **GraphRAG service** (`backend/Dockerfile.graphrag`) that was running externally on Azure - not containerised locally
- A Jenkins pipeline (`Jenkinsfile_Deploy_App`) that was wired for one service only, using **placeholder Nginx images** in `images.yaml`
- Helm charts for three services but with wrong ports, no secret injection, and no probes
- Terraform that provisioned ECR, EKS, RDS, ElastiCache, S3, and Secrets Manager - but the application was not actually connected to any of it
- No `docker-compose.yml` entries for PostgreSQL, Redis, or GraphRAG

---

## 2. Branch Setup

We were working on the `deployment/dev-jenkins` branch. The initial checkout failed because of local uncommitted changes.

**What we did:**
```bash
git reset --hard HEAD
git clean -fd
git fetch origin
git switch deployment/dev-jenkins
```

The `GIT_BRANCH` default in `Jenkinsfile_Deploy_App` was also updated to `deployment/dev-jenkins` so Jenkins picks the right branch automatically.

---

## 3. Docker Images - Replacing Stub Nginx with Real Services

### Problem
`deploy/ecs-app/docker/build-registry/images.yaml` pointed to stub Nginx Dockerfiles for all three services. Nothing real was being built or pushed to ECR.

### What we changed

**`images.yaml`** - pointed each entry to the real Dockerfile and correct build context:

```yaml
images:
  - service: midas-web-frontend-svc
    context: frontend
    dockerfile: Dockerfile
    ecr_repository_suffix: midas-web-frontend-svc

  - service: midas-api-backend-svc
    context: backend
    dockerfile: Dockerfile
    ecr_repository_suffix: midas-api-backend-svc

  - service: midas-graph-svc
    # Build context must be repo root because Dockerfile.graphrag copies from backend/graphrag_service/
    context: .
    dockerfile: backend/Dockerfile.graphrag
    ecr_repository_suffix: midas-graph-svc
```

**`.dockerignore`** - created at repo root to keep the GraphRAG build context lean (it uses `.` as context, so without this the entire repo would be sent to Docker daemon).

**`docker-build-matrix.sh`** and **`push-images-ecr.sh`** - fixed platform-specific `yq` binary download (the original only handled Linux AMD64; we added macOS ARM/AMD64 and Linux ARM64 cases).

---

## 4. Local Development Setup

### GraphRAG - moved from Azure to local Docker

The GraphRAG service was previously running as an Azure Web App. We containerised it locally so the full stack runs in Docker Compose.

**`docker-compose.yml` additions:**

| Service | Image | Port | Purpose |
|---|---|---|---|
| `postgres` | `postgres:15-alpine` | `5433:5432` | Local database (host port 5433 to avoid conflict with system Postgres) |
| `redis` | `redis:7-alpine` | `6379:6379` | Local cache and session store |
| `graphrag` | Built from `backend/Dockerfile.graphrag` | `8001:8001` | GraphRAG knowledge service |

The `backend` service was updated to `depends_on` all three and gets these injected at runtime:
```
DATABASE_URL=postgresql://midas_pg:midas_local@postgres:5432/midas_dev
REDIS_URL=redis://redis:6379/0
SESSION_REDIS_URL=redis://redis:6379/0
GRAPHRAG_SERVICE_URL=http://graphrag:8001
```

### Hybrid AWS override

`docker-compose.aws.yml` was created as an optional override. When you have VPN access to the AWS VPC, you can run:
```bash
docker compose -f docker-compose.yml -f docker-compose.aws.yml up
```
This disables the local `postgres` and `redis` containers and points the backend at the real AWS RDS and ElastiCache endpoints instead.

### `backend/.env` - local mode configuration

The `.env` file is structured so that:
- `DATABASE_URL` and `REDIS_URL` point to `localhost` (for running the backend outside Docker)
- `AWS_RDS_POSTGRES_SECRET_ID` and `SESSION_ELASTICACHE_SECRET_ARN` are **left blank** - if these are set, the backend tries to fetch credentials from Secrets Manager on startup, which fails locally without AWS credentials

When running via `docker compose up`, the `environment:` block in `docker-compose.yml` overrides these with the correct Docker-internal hostnames (`postgres`, `redis`).

---

## 5. AWS Services - What We Use and Where

| Service | Local | Jenkins / EKS |
|---|---|---|
| **PostgreSQL** | Docker container (`postgres:15-alpine`) | AWS RDS (`midas-dev-us-east-1-pg-*`) |
| **Redis** | Docker container (`redis:7-alpine`) | AWS ElastiCache (`master.midas-dev-redis.*`) |
| **S3** | AWS (always) | AWS (always) |
| **Secrets Manager** | Push from laptop; read in EKS | Read in Jenkins; synced to K8s secret |
| **ECR** | N/A locally | Images pushed here by Jenkins |
| **EKS** | N/A locally | Helm deploys here |

The S3 bucket (`midas-dev-us-east-1-test-20260404180513813900000001`) is used for file uploads and is always AWS - no local substitute needed.

---

## 6. Secrets Management Strategy

### The problem
`backend/.env` is gitignored. Jenkins never has it after `git clone`. We needed a way to get credentials into EKS pods without committing secrets to git.

### The solution - two-step flow

**Step 1 - Developer machine (one-time, or whenever `.env` changes):**
```bash
cd bu-analytics-gen-ai-midas
export AWS_ACCESS_KEY_ID=...
export AWS_SECRET_ACCESS_KEY=...
export AWS_SESSION_TOKEN=...
./deploy/scripts/ci/populate-secrets.sh dev
```
This reads `backend/.env`, converts it to JSON, and pushes it to AWS Secrets Manager under the key `midas-dev-us-east-1/app`.

**Step 2 - Jenkins / Helm deploy (automatic):**
`helm-deploy-releases.sh` runs `aws eks update-kubeconfig`, then fetches the secret from Secrets Manager and creates/updates a Kubernetes Secret named `midas-app-secret` in the `midas-apps` namespace. All three pods use `envFrom.secretRef` to load this secret.

### Why not read `.env` in Jenkins?
`.env` is gitignored by design - it contains credentials. Jenkins clones the repo fresh each run and will never have the file. The Secrets Manager is the single source of truth for production credentials.

---

## 7. Jenkins Pipeline - What We Added and Why

The pipeline (`Jenkinsfile_Deploy_App`) already had the skeleton. Here is what we added or changed:

### New stage: `Terraform init - ecs-app (outputs only)`
Reads Terraform state after `apply` and writes ECR URLs and the EKS cluster name into `deploy/.ci/terraform-env.sh`. This file is sourced by subsequent stages so they know where to push images and which cluster to deploy to.

### New stage: `Verify Secrets Manager`
A lightweight check - just calls `aws secretsmanager describe-secret` to confirm `midas-dev-us-east-1/app` exists before we proceed to build and deploy. Fails fast with a clear error if the secret hasn't been populated yet.

### New stage: `Helm deploy - EKS`
Controlled by the `ENABLE_HELM_DEPLOY` boolean parameter. When enabled:
1. Runs `aws eks update-kubeconfig` to authenticate kubectl
2. Verifies EKS API connectivity (pre-flight check)
3. Syncs Secrets Manager → `midas-app-secret` K8s secret
4. Runs `helm upgrade --install` for all three services

### Full pipeline stage order
```
Checkout
  → Auth Check (non-dev only)
  → Get customer mapping
  → Create deploy role
  → Terraform plan (ecs-app)
  → Approve deploy?
  → Terraform apply (ecs-app)
  → Terraform init - ecs-app (outputs only)
  → Verify Secrets Manager
  → Docker build - MIDAS images
  → Push images to ECR
  → Helm deploy - EKS  (if ENABLE_HELM_DEPLOY=true)
```

---

## 8. Helm / EKS Deployment

### What was broken in the Helm charts

- All three charts had wrong `containerPort` values (were set to 80 for backend/graphrag)
- No `envFrom` / `secretRef` - pods had no way to receive credentials
- No liveness or readiness probes
- Frontend had no `BACKEND_UPSTREAM` env var
- Backend had no `GRAPHRAG_SERVICE_URL` env var

### What we fixed

**`midas-api-backend-svc`** - port 8000, `envFrom` from `midas-app-secret`, probes on `/health`, `GRAPHRAG_SERVICE_URL` pointing to in-cluster GraphRAG DNS.

**`midas-graph-svc`** - port 8001, `envFrom` from `midas-app-secret`, probes on `/health`, `GRAPHRAG_SERVICE_PORT=8001`.

**`midas-web-frontend-svc`** - port 80, `BACKEND_UPSTREAM` pointing to backend in-cluster DNS, probes on `/`.

### In-cluster service DNS

```
Backend:  http://midas-api-backend-svc.midas-apps.svc.cluster.local:8000
GraphRAG: http://midas-graph-svc.midas-apps.svc.cluster.local:8001
```

### EKS access - `midas-deployer-role`

The Jenkins pipeline assumes the `midas-deployer-role` IAM role (via `withAWS`). This role already had EKS cluster admin access configured outside of Terraform. We confirmed this when a Terraform attempt to add `aws_eks_access_entry` failed with `ResourceInUseException` - meaning the access entry already existed.

---

## 9. Mistakes Made and How We Fixed Them

### 9.1 - Added `aws_eks_access_entry` to Terraform, then had to revert it

**What happened:** We added `aws_eks_access_entry` and `aws_eks_access_policy_association` resources to `deploy/ecs-app/modules/eks/main.tf` to grant `midas-deployer-role` cluster admin access.

**The error:**
```
Error: creating EKS Access Entry: ResourceInUseException:
The specified access entry resource is already in use on this cluster.
```

**The fix:** The role already had access - it was configured manually or by a prior Terraform run that is no longer tracked in state. We reverted the `main.tf` changes entirely. Lesson: don't add Terraform resources for things that already exist in AWS without first importing them into state.

---

### 9.2 - `populate-secrets.sh` tried to read `.env.backup` which had UTF-16 encoding

**What happened:** The script originally fell back to `backend/.env.backup`. That file had been saved with UTF-16 encoding (wide characters with null bytes), which caused the Python JSON parser to fail silently or produce garbage.

**The fix:** Changed the script to read `backend/.env` (UTF-8, always correct) and removed `.env.backup` from the fallback chain entirely.

---

### 9.3 - Jenkins stage tried to run `kubectl` before kubeconfig was set up

**What happened:** The `Sync Secrets Manager → K8s` stage called `kubectl create namespace` and `kubectl apply` - but `aws eks update-kubeconfig` had not been run yet at that point in the pipeline. Result: `error: You must be logged in to the server`.

**The fix:** Removed all `kubectl` calls from `populate-secrets.sh`. The K8s secret sync now lives exclusively in `helm-deploy-releases.sh`, which runs `aws eks update-kubeconfig` first and verifies connectivity before touching the cluster. The Jenkins stage was renamed to `Verify Secrets Manager` and only checks that the Secrets Manager secret exists - no kubectl involved.

---

### 9.4 - Docker port conflict on local machine

**What happened:** `docker compose up` failed with:
```
listen tcp 0.0.0.0:5432: bind: address already in use
```
A system-level PostgreSQL instance was already running on port 5432.

**The fix:** Changed the `postgres` service host port mapping in `docker-compose.yml` from `5432:5432` to `5433:5432`. The container still listens on 5432 internally; only the host-side port changed.

---

### 9.5 - Backend crashed locally with `NoCredentialsError`

**What happened:** After adding PostgreSQL and Redis containers, the backend still crashed on startup:
```
botocore.exceptions.NoCredentialsError: Unable to locate credentials
```

**Root cause:** `backend/.env` had `AWS_RDS_POSTGRES_SECRET_ID` and `SESSION_ELASTICACHE_SECRET_ARN` set to real values. The backend's startup code saw these and tried to call AWS Secrets Manager to fetch database credentials - but the local Docker container had no AWS credentials.

**The fix:** Cleared both fields in `backend/.env` for local mode:
```
AWS_RDS_POSTGRES_SECRET_ID=
SESSION_ELASTICACHE_SECRET_ARN=
```
With these blank, the backend uses the `DATABASE_URL` and `REDIS_URL` injected directly by `docker-compose.yml` instead.

---

### 9.6 - `images.yaml` build context wrong for GraphRAG

**What happened:** The GraphRAG `Dockerfile.graphrag` uses `COPY backend/graphrag_service/ ...` - it references paths relative to the repo root. Setting `context: backend` as the build context meant Docker couldn't find those paths and the build failed.

**The fix:** Set `context: .` (repo root) for the `midas-graph-svc` entry in `images.yaml`, and created a `.dockerignore` at the repo root to avoid sending the entire repository to the Docker daemon unnecessarily.

---

### 9.7 - `yq` download in CI scripts was Linux-only

**What happened:** `docker-build-matrix.sh`, `push-images-ecr.sh`, and `helm-deploy-releases.sh` all downloaded `yq_linux_amd64` unconditionally. Running on macOS (or a Linux ARM Jenkins agent) would download the wrong binary and fail silently or with a cryptic exec error.

**The fix:** Added platform detection using `uname -s` and `uname -m` with a `case` statement covering `linux_x86_64`, `linux_aarch64`, `darwin_x86_64`, and `darwin_arm64`.

---

## 10. Quick Reference

### Run locally (full stack)

```bash
cd bu-analytics-gen-ai-midas
docker compose up --build
```

Services:
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- GraphRAG: http://localhost:8001
- PostgreSQL: localhost:5433
- Redis: localhost:6379

### Run locally with AWS RDS + ElastiCache (requires VPN)

```bash
docker compose -f docker-compose.yml -f docker-compose.aws.yml up --build
```

### Push secrets to AWS Secrets Manager (from your laptop)

```bash
export AWS_ACCESS_KEY_ID=...
export AWS_SECRET_ACCESS_KEY=...
export AWS_SESSION_TOKEN=...
cd bu-analytics-gen-ai-midas
./deploy/scripts/ci/populate-secrets.sh dev
```

Run this whenever `backend/.env` changes. Jenkins reads from Secrets Manager, not from the file.

### Trigger Jenkins pipeline

In the Jenkins UI, run `Jenkinsfile_Deploy_App` with:
- `CUSTOMER`: `midas`
- `ENVIRONMENT`: `dev`
- `IMAGE_TAG`: your tag (e.g. `v1.0.0` or `latest`)
- `GIT_BRANCH`: `deployment/dev-jenkins`
- `ENABLE_HELM_DEPLOY`: `true` (if Jenkins agent has network path to EKS private API)

### Manual Helm deploy (from a machine with EKS access)

```bash
aws eks update-kubeconfig --name midas-eks-dev --region us-east-1
cd bu-analytics-gen-ai-midas/deploy/ecs-app
. ../.ci/terraform-env.sh
IMAGE_TAG=latest EKS_CLUSTER_NAME=midas-eks-dev \
  ../../scripts/ci/helm-deploy-releases.sh
```

### Check running pods

```bash
kubectl get pods -n midas-apps
kubectl logs -n midas-apps deployment/midas-api-backend -f
```

# Local Docker Compose stack

Run the full ARB - AI Assistant stack in containers on your machine. Use this folder when you want **Docker Compose** instead of bare-metal `make start`.

| Command | What it does |
|---------|----------------|
| `make build-dockers` | Compile gRPC clients and build all images |
| `make start-local-docker` | Start the compose stack (detached) |
| `make stop-local-docker` | Stop and remove containers |
| `make restart-local-docker` | Stop then start |
| `make start-local-docker BUILD=1` | Rebuild images while starting |
| `make start-local-docker iam` | Start one service (and its dependencies) |

Open the UI at http://127.0.0.1:8802 after the stack is up.

## Prerequisites

1. **Docker Engine** with Compose v2 (`docker compose version`).
2. **AWS credentials** in `infra/envs/dev/.env.aws` (copy from `infra/envs/dev/.env.aws.example`).
3. **Optional per-service secrets** in `*/server/.env.local` (copy from `*/server/.env.example`).
4. **Frontend auth** (recommended): `infra/local-docker-compose/.env.local` from `.env.local.example` (`AUTH_SECRET`, IAM bootstrap).

Bare-metal dev (`make start`) uses `infra/envs/dev/local.env` for loopback gRPC hosts. Containers use `infra/envs/dev/compose.env` for Docker network hostnames (`iam`, `storage`, …).

## Services and ports

| Service | Compose name | Port | Image | AWS / data dependencies |
|---------|--------------|------|-------|-------------------------|
| IAM | `iam` | 8803 | `arb-iam-service:local` | DynamoDB (IAM tables) |
| Solutions | `solutions` | 8804 | `arb-solutions-service:local` | DynamoDB (solutions + history) |
| Storage | `storage` | 8805 | `arb-storage-service:local` | SQLite volume (`storage_data`), S3 `exlservice-arb-general` |
| General AI agent | `general-ai-agent` | 8806 | `arb-general-ai-agent-service:local` | Amazon Bedrock |
| Notification | `notification` | 8807 | `arb-notification-service:local` | SNS notifications topic |
| Collaboration | `collaboration` | 8808 | `arb-collaboration-service:local` | DynamoDB (aliases + discussions) |
| Document storage | `document-storage` | 8809 | `arb-document-storage-service:local` | DynamoDB registry/groups, S3 docstore, OpenSearch, Bedrock embeddings |
| Arch diagram agent | `arch-diagram-agent` | 8810 | `arb-arch-diagram-agent-service:local` | Bedrock, DynamoDB jobs; gRPC to document-storage + storage |
| Frontend | `frontend` | 8802 | `arb-frontend:local` | gRPC to all backends above |

**Not in compose:** `aspire.svc` (app-composition host, port 8801) — use `make start aspire` for bare-metal only.

## Per-service container requirements

Each Python service image is built from `*/server/Dockerfile` with repository root as context. Runtime needs:

| Service | Required config | Notes |
|---------|-----------------|-------|
| **iam** | `app_config.toml` (baked in image), AWS creds | `IAM_AUTO_BOOTSTRAP_ADMIN_ON_EMPTY=false` in compose |
| **solutions** | `app_config.toml`, AWS creds | `SOLUTIONS_APP_CONFIG_PATH=./app_config.toml` |
| **storage** | AWS creds, persistent volume | `STORAGE_DATABASE_PATH=/app/data/storage.db` on named volume |
| **notification** | AWS creds | SNS startup check skipped locally |
| **collaboration** | `app_config.toml`, AWS creds | DynamoDB startup check skipped locally |
| **document-storage** | `app_config.toml`, AWS creds | DynamoDB startup check skipped locally |
| **general-ai-agent** | AWS creds | Bedrock access via task/instance credentials |
| **arch-diagram-agent** | `app_config.toml`, AWS creds | Calls `document-storage` and `storage` by compose hostname |
| **frontend** | `compose.env` + optional `.env.local` | `APP_ENV=dev`, `APP_TARGET=local`, `AUTH_TRUST_HOST=true` |

## Layout

| File | Purpose |
|------|---------|
| `docker-compose.yml` | Full local stack definition |
| `.env.example` | Compose-level env template |
| `.env.local.example` | Frontend `AUTH_SECRET` and IAM bootstrap for containers |

Canonical Dockerfiles remain beside each service (`iam.svc/server/Dockerfile`, `frontend/Dockerfile`, …). Image build orchestration: `make/build_docker.py` and `infra/containers/scripts/rebuild_all.py`.

## Manual compose (equivalent to make targets)

From the **repository root**:

```bash
docker compose -f infra/local-docker-compose/docker-compose.yml up -d
docker compose -f infra/local-docker-compose/docker-compose.yml down
docker compose -f infra/local-docker-compose/docker-compose.yml ps
```

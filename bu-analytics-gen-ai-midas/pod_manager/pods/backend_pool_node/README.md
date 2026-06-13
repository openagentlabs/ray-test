# backend_pool_node

Minimal HTTP **backend pool node** for routing-tier E2E tests. Each instance is one routable member of the **backend pool** (registered in Postgres `pm_backend_pool`, assigned to users via `router.svc`).

Displays `BACKEND_POOL_NODE_NAME` from the environment (Docker Compose service name or StatefulSet pod name).

## REST API

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/me` | Identity + pod (requires `x-user-sub` from ext_authz) |
| GET | `/api/v1/ping` | Lightweight liveness for leased traffic |
| GET | `/api/me` | Alias of `/api/v1/me` |
| GET | `/healthz` | Health (direct probe) |

## Run locally

```bash
# From repo root
docker build -t backend-pool-node:local ./pods/backend_pool_node
docker run --rm -p 8080:8080 -e BACKEND_POOL_NODE_NAME=backend-pool-node-0 backend-pool-node:local
```

## Kubernetes

See `pods/backend_pool_node/k8s/statefulset.yaml` — headless Service DNS:
`backend-pool-node-0.backend-pool-node.<namespace>.svc.cluster.local:8080`

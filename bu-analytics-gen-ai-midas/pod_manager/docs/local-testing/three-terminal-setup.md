# Three-terminal local setup

This is the recommended layout when you have **three terminals**: one for the **Docker stack**, one for the **operator CLI**, and one for the **Next.js test client**.

## Overview

```mermaid
flowchart LR
  T1["Terminal 1\nStack"]
  T2["Terminal 2\nCLI"]
  T3["Terminal 3\nWeb"]

  T1 --> DDB[(Postgres :5432)]
  T1 --> R[router :8804 / :9000]
  T1 --> E[Envoy :10000]
  T1 --> P[pods :18080+]

  T2 -->|gRPC| R
  T2 -->|HTTP optional| E

  T3 -->|gRPC lease| R
  T3 -->|BFF HTTP| E
```

## Prerequisites

| Tool | Used for |
|------|----------|
| Docker + Compose | Stack images, networking, Postgres, and `seed_local_pool.sh` (runs `psql` inside the `postgres` container) |
| `curl` | Smoke tests and manual HTTP checks |
| [uv](https://docs.astral.sh/uv/) | CLI and router.svc Python |
| Node.js 20+ | `test_client_nextjs` and `router.svc/client_ts` build |

## Terminal 1 — Stack

**Working directory:** repository root (`pod_manager/`).

### Start (detached, fresh data)

```bash
./infra/docker/start-local.sh -r -s -d
```

Optional: add **`-t`** to run automated smoke tests when ready:

```bash
./infra/docker/start-local.sh -r -s -d -t
```

### What this script does

1. Stops prior `pod-manager-local` (and legacy `docker`) compose projects  
2. Starts **Postgres** on port 5432 and waits for it to accept connections  
3. Runs `router.svc/server/tools/seed_local_pool.sh` — bootstraps the `pm_*` schema (`CREATE TABLE IF NOT EXISTS`) and seeds the pool via `psql`  
4. `docker compose up --build -d` for router, Envoy, login-pod, backend nodes (router auto-creates any remaining `pm_*` tables at startup)  

### Follow logs (same terminal or another)

```bash
docker compose -f infra/docker/docker-compose.local.yml -p pod-manager-local logs -f
```

### Stop stack

```bash
docker compose -f infra/docker/docker-compose.local.yml -p pod-manager-local down
```

Or restart clean:

```bash
./infra/docker/start-local.sh -r
```

### Verify stack is up

| Check | Command |
|-------|---------|
| Envoy health | `curl -s http://localhost:8080/healthz` → `ok` |
| gRPC port | `nc -zv localhost 8804` |
| API port | `nc -zv localhost 10000` |

---

## Terminal 2 — Operator CLI

**Working directory:** `pod_manager_cli/`.

### One-time install

```bash
cd pod_manager_cli
uv sync
```

### Environment (every session)

```bash
export POD_MANAGER_HOST=localhost
export POD_MANAGER_PORT=8804
export ENVOY_URL=http://localhost:10000
```

### Typical session

```bash
uv run pod-manager pool
uv run pod-manager claim --sub alice@example.com
uv run pod-manager route --sub alice@example.com
uv run pod-manager e2e --sub alice@example.com
uv run pod-manager release --sub alice@example.com
```

Full command reference: [cli-operator.md](cli-operator.md).

**Note:** CLI HTTP commands use header `x-test-sub` (dev mode). They do not use the browser cookie.

---

## Terminal 3 — Web test client

**Depends on:** Terminal 1 running; **gRPC client built** once.

### One-time build of TypeScript gRPC client

```bash
cd router.svc/client_ts
npm ci
npm run build
```

### Install and run Next.js

```bash
cd test_client_nextjs
npm install
```

Environment (defaults usually work if stack uses standard ports):

```bash
export NEXT_PUBLIC_ENVOY_URL=http://localhost:10000
export POD_MANAGER_GRPC_HOST=localhost
export POD_MANAGER_GRPC_PORT=8804
npm run dev
```

Open **http://localhost:3000**.

User flows: [web-test-client.md](web-test-client.md).

---

## Startup order

```mermaid
sequenceDiagram
  participant Dev as Developer
  participant T1 as Terminal 1
  participant T2 as Terminal 2
  participant T3 as Terminal 3

  Dev->>T1: start-local.sh -r -s -d
  T1-->>Dev: ports 5432, 8804, 10000 ready
  Dev->>T2: export env + pod-manager pool
  T2-->>Dev: lists backend + login pods
  Dev->>T3: npm run dev
  T3-->>Dev: http://localhost:3000
```

1. **Always start Terminal 1 first** and wait until `8804` and `10000` accept connections.  
2. Terminal 2 and 3 can start in any order after that.  
3. Re-run **`-r`** on Terminal 1 if you change the Postgres seed or table prefix — then refresh browser and re-acquire leases.

## Environment reference

| Variable | Default (local) | Set in |
|----------|-----------------|--------|
| `COMPOSE_PROJECT` | `pod-manager-local` | Terminal 1 (optional) |
| `DATABASE_URL` | `postgresql://postgres:postgres@postgres:5432/midas` | `docker-compose.local.yml` |
| `POD_MANAGER_POSTGRES_TABLE_PREFIX` | `pm_` | `docker-compose.local.yml` |
| `POD_MANAGER_APP_SERVICE_NAME` | `router-svc` | `start-local.sh` |
| `POD_MANAGER_HOST` | `localhost` | Terminal 2 |
| `POD_MANAGER_PORT` | `8804` | Terminal 2 |
| `ENVOY_URL` | `http://localhost:10000` | Terminal 2 |
| `NEXT_PUBLIC_ENVOY_URL` | `http://localhost:10000` | Terminal 3 |
| `POD_MANAGER_GRPC_HOST` | `localhost` | Terminal 3 |
| `POD_MANAGER_GRPC_PORT` | `8804` | Terminal 3 |

## Parallel testing tips

- Use **different emails** per browser profile or CLI `--sub` (e.g. `alice@example.com`, `bob@example.com`) — only **two** backend leases are seeded locally.  
- Third user should see **pool full** → web `/wait` or CLI resource exhausted.  
- CLI `release` frees a backend for another user without restarting the stack.

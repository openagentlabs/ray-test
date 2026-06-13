# Local testing hub

Run the full **routing tier** on your laptop: Postgres assignment store, **router.svc** (gRPC + ext_authz), **Envoy**, a shared **login pod**, and two **backend pool** nodes. Validate behavior with automated smoke tests, the **operator CLI**, or the **Next.js test client**.

## What you are testing

| Concern | How local stack proves it |
|---------|---------------------------|
| **Identity → route** | Only verified `sub` (email) selects upstream; no client routing headers |
| **Login pool** | Users without a backend lease hit `login-pod` |
| **Backend lease** | `AcquireLease` assigns one exclusive backend pod per user |
| **Fail closed** | API calls without a lease return `403 no_backend_lease` |
| **Envoy data plane** | ext_authz + dynamic forward proxy; bytes do not pass through router.svc |

## Three terminals (recommended)

| Terminal | Directory / command | Purpose |
|----------|---------------------|---------|
| **1 — Stack** | `./infra/docker/start-local.sh -r -s -d` | Postgres, router, Envoy, pods |
| **2 — CLI** | `cd pod_manager_cli` → `uv run pod-manager …` | gRPC pool/lease/HTTP smoke |
| **3 — Web** | `cd router.svc/client_ts && npm run build` then `cd test_client_nextjs && npm run dev` | Browser flows via BFF |

Detailed setup: [three-terminal-setup.md](three-terminal-setup.md).

## Ports (host)

| Port | Service | Use |
|------|---------|-----|
| **5432** | Postgres | Routing state (`pm_*` tables) |
| **8804** | router.svc gRPC | Control plane API (CLI, Next lease RPCs) |
| **9000** | router.svc ext_authz | Envoy → gRPC Check (internal; also published locally) |
| **10000** | Envoy HTTP | API ingress (browser BFF target, CLI HTTP) |
| **8080** | Envoy health | `/healthz` (no ext_authz) |
| **18080** | backend-pool-node-0 | Direct pod access (debug) |
| **18081** | backend-pool-node-1 | Direct pod access (debug) |
| **18082** | login-pod | Direct login service (debug) |
| **3000** | Next.js dev | Test UI (terminal 3) |

## One-command stack + smoke tests

```bash
./infra/docker/start-local.sh -r -s -d -t
```

- `-r` — tear down old compose project and reset the Postgres database  
- `-s` — start (required flag)  
- `-d` — detached  
- `-t` — run [automated-tests.md](automated-tests.md) after services are healthy  

## Minimal manual checks

```bash
# Pool registry (gRPC)
cd pod_manager_cli && uv sync
export POD_MANAGER_HOST=localhost POD_MANAGER_PORT=8804 ENVOY_URL=http://localhost:10000
uv run pod-manager pool

# HTTP without lease → login pod 403
curl -s -H 'x-test-sub: alice@example.com' http://localhost:10000/api/v1/me

# Lease + HTTP → backend JSON
uv run pod-manager claim --sub alice@example.com
curl -s -H 'x-test-sub: alice@example.com' http://localhost:10000/api/v1/me
```

## Guide map

1. [three-terminal-setup.md](three-terminal-setup.md) — start order, env vars, prerequisites  
2. [components.md](components.md) — each container/service in isolation  
3. [architecture-and-flows.md](architecture-and-flows.md) — diagrams and end-to-end flows  
4. [apis-and-clients.md](apis-and-clients.md) — RPCs, REST paths, client libraries  
5. [web-test-client.md](web-test-client.md) — UI pages and user journeys  
6. [cli-operator.md](cli-operator.md) — `pod-manager` commands  
7. [automated-tests.md](automated-tests.md) — `test-local.sh`  
8. [troubleshooting.md](troubleshooting.md) — stale seed, ports, cookies  

## Production vs local

| Local | Production (EKS) |
|-------|------------------|
| Cognito replaced by email cookie + `x-test-sub` (`POD_MANAGER_AUTH_DEV_MODE=true`) | Cognito JWT in `Authorization` |
| Local `postgres:16` container | Shared backend Postgres (RDS) |
| Fixed seed: 2 backends + 1 login pod | Reconciliation discovers cluster pods |
| Next BFF on `:3000` | SPA behind ALB → Envoy |

Deploy path: [../../infra/README.md](../../infra/README.md).

# Troubleshooting (local stack)

Symptoms, causes, and fixes when running the [three-terminal setup](three-terminal-setup.md) or [automated tests](automated-tests.md).

## Quick recovery

Most “weird state” issues:

```bash
./infra/docker/start-local.sh -r -s -d -t
```

This tears down compose, recreates the Postgres database, re-seeds pools, rebuilds images, and runs smoke tests.

---

## Stale Postgres seed

### Symptom

`pod-manager pool` shows `no-pod-available-pool-node-0` or `no_pod_available_pool`.

### Cause

Old seed from a previous architecture (overflow pool). The database was not reset.

### Fix

```bash
./infra/docker/start-local.sh -r -s -d
./infra/docker/test-local.sh   # should report backend-pool-node-0/1 + login-pod
```

---

## Port already in use

### Symptom

Compose fails to bind `5432`, `8804`, `10000`, `8080`, or `1808x`.

### Cause

Another container or process holds the port.

### Fix

`start-local.sh` stops **other** containers publishing those ports (not same compose project). Manually:

```bash
docker ps --filter publish=10000
# stop conflicting container
```

Or change host mappings in `infra/docker/docker-compose.local.yml` (then update env docs in your terminals).

---

## gRPC `UNAVAILABLE` / CLI exit 2

### Symptom

`error: ... UNAVAILABLE` from `pod-manager`.

### Cause

router container not running or still starting.

### Fix

```bash
docker compose -f infra/docker/docker-compose.local.yml -p pod-manager-local ps
docker compose -f infra/docker/docker-compose.local.yml -p pod-manager-local logs router --tail 50
nc -zv localhost 8804
```

Wait for healthcheck; router depends on Postgres.

---

## Envoy exits or 503 from API

### Symptom

`:10000` connection refused; smoke test warns on health listener.

### Cause

Envoy starts only after router is healthy; bad ext_authz target or config validate failure.

### Fix

```bash
docker compose -f infra/docker/docker-compose.local.yml -p pod-manager-local logs envoy --tail 80
docker build ./envoy   # validates config
```

Check `ENVOY_EXT_AUTHZ_HOST=router` and port `9000` in compose.

---

## `claim` — resource exhausted

### Symptom

`No free nodes in backend_pool` with fewer than two users.

### Cause

All backend pods claimed; or stale assignments in Postgres.

### Fix

```bash
uv run pod-manager pool
uv run pod-manager release --sub alice@example.com
# or full reset:
./infra/docker/start-local.sh -r -s -d
```

Local seed has **2** backends — third user should fail until one releases.

---

## Web: `no_backend_lease` on `/home` after lease

### Symptom

`/home` shows 403 or redirects to `/lease` immediately after acquire.

### Causes

| Cause | Fix |
|-------|-----|
| Cookie not set (login failed) | Re-login at `/`; check email format |
| Different email than lease | Session email must match gRPC `sub` |
| Released in CLI | Re-acquire in UI or CLI |
| Stack restarted (Postgres cleared) | Acquire lease again |

Check session:

```bash
curl -s http://localhost:3000/api/session --cookie "pod_manager_user=alice@example.com"
```

---

## Web: login 500 or `Unexpected end of JSON input`

### Symptom

`POST /api/auth/login` returns **500**; Next.js server log shows **`SyntaxError: Unexpected end of JSON input`**.

### Cause

The BFF proxied **`POST /login`** to Envoy **without** identity. ext_authz denied the request (**403**, empty body). The route tried to parse empty JSON.

### Fix

Ensure **`test_client_nextjs/src/app/api/auth/login/route.ts`** sends **`x-test-sub: <email>`** when calling Envoy (required for first login — no cookie yet). See [web-test-client.md — BFF login requirement](web-test-client.md#bff-login-requirement-local-dev).

Confirm the stack is up and dev mode is on:

```bash
curl -s -X POST http://localhost:10000/login \
  -H 'Content-Type: application/json' \
  -H 'x-test-sub: alice@example.com' \
  -d '{"user_name":"alice@example.com","user_password":"x"}'
```

---

## Web: login works on direct port but fails via Envoy

### Symptom

`18082/login` OK; BFF or Envoy `POST /login` returns **403**.

### Cause

ext_authz requires identity on the Envoy path. Missing **`x-test-sub`** (first login) or session cookie (subsequent API calls).

### Fix

- Use Next **`/api/auth/login`** (BFF must send **`x-test-sub`** — see above).  
- CLI/curl through Envoy: add **`-H 'x-test-sub: user@example.com'`**.  
- Direct pod port **18082** bypasses Envoy (debug only).

---

## Next.js: cannot find `@router/client-ts`

### Symptom

Build error importing from `router.svc/client_ts/dist`.

### Fix

```bash
cd router.svc/client_ts && npm ci && npm run build
```

---

## `TypeError: unhashable type: 'list'` (CLI pool)

### Symptom

`pod-manager pool` crashes.

### Cause

Old client/server mismatch — upgrade repo and `uv sync` in `pod_manager_cli`.

### Fix

```bash
cd pod_manager_cli && uv sync
cd ../router.svc/client_py && uv sync
./infra/docker/start-local.sh -r -s -d
```

---

## Smoke test: POST /login via Envoy

### Symptom

Single failure on “POST /login via Envoy” without `x-test-sub`.

### Expected

Script sends `x-test-sub` for Envoy login check. Without it, 403 is correct (fail closed).

---

## Getting help

| Evidence to collect |
|---------------------|
| `docker compose -p pod-manager-local ps` |
| `docker compose -p pod-manager-local logs router envoy --tail 100` |
| `uv run pod-manager pool` |
| Output of `./infra/docker/test-local.sh` |

---

## Related

- [components.md](components.md) — expected ports and roles  
- [architecture-and-flows.md](architecture-and-flows.md) — expected request behavior

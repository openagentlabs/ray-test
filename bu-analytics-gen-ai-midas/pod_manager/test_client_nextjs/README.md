# test_client_nextjs

Next.js test UI for **login pod pool** + **backend lease** flows (shadcn/ui, dark/light theme).

## Prerequisites

- Local stack: `./infra/docker/start-local.sh -r -s -d` from repo root
- Built `@router/client-ts`: `cd ../router.svc/client_ts && npm run build`

Full guide: [docs/local-testing/web-test-client.md](../docs/local-testing/web-test-client.md) (three-terminal setup, user flows, BFF).

## Run

```bash
npm install
export NEXT_PUBLIC_ENVOY_URL=http://localhost:10000
export POD_MANAGER_GRPC_HOST=localhost
export POD_MANAGER_GRPC_PORT=8804
npm run dev
```

## Pages

| Route | Purpose |
|-------|---------|
| `/` | Login (email + password → sets `pod_manager_user` cookie) |
| `/lease` | Acquire exclusive backend lease |
| `/wait` | 60s countdown + auto-retry when pool full |
| `/home` | `GET /api/v1/me` on leased backend via BFF → Envoy; release lease |
| `/lease` | Acquire lease; **Try backend API** shows `no_backend_lease` before acquire |
| `/debug` | Manual API smoke tests |

Login is proxied via `/api/auth/login` so the session cookie is on the Next origin (`localhost:3000`). API traffic to Envoy uses `/api/backend/*`, which forwards that cookie server-side to `NEXT_PUBLIC_ENVOY_URL`.

**Local dev:** the login BFF must send **`x-test-sub`** to Envoy on first login (no cookie yet). See [docs/local-testing/web-test-client.md](../docs/local-testing/web-test-client.md#bff-login-requirement-local-dev).

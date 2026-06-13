# Fix-up plan — login pool / test client / infra / dead code

## Phase 1 — Functional gaps (done)

| # | Item | Fix | Status |
|---|------|-----|--------|
| 1 | Test client cookie → Envoy | BFF `/api/backend/*` | Done |
| 2 | Debug page Envoy call | `/api/backend/api/me` | Done |
| 3 | Terraform `login_pod_pool` | Table + dev suffixes | Done |
| 4 | Helm login-pod + env | Deployment/Service + env vars | Done |
| 5 | ECR `login-pod` | dev `ecr_repository_names` | Done |
| 6 | Legacy `NO_POD_*` | Removed | Done |
| 7 | Docs | docs index + test client README | Done |

## Phase 2 — Remove unused / deprecated code

| # | Item | Action | Status |
|---|------|--------|--------|
| 8 | `ClaimPod` / `ReleasePod` RPC + messages | Remove from `pool.proto`; regenerate stubs | Done |
| 9 | Server wrappers `claim_pod` / `release_pod` | Delete; servicer methods removed | Done |
| 10 | `client_ts` `claimPod` / `releasePod` / `ClaimResult` | Use `acquireLease` / `releaseLease` / `LeaseResult` only | Done |
| 11 | `client_py` `claim_pod` / `release_pod` | `acquire_lease` / `release_lease`; `LeaseResult` | Done |
| 12 | `pod_manager_cli` | Wire `claim`/`release` commands to lease RPCs | Done |
| 13 | Echo scaffold (`solutions.v1.Echo`) | Remove proto, handler, servicer, generated stubs | Done |
| 14 | `map_handler_result` | Move to `grpc_transport/handler_result.py`; drop echo servicer | Done |
| 15 | Stale docs | Client READMEs → lease API names | Done |

### Keep (not dead)

- `GetPoolStatus`, `Heartbeat`, config RPCs — used by CLI/ops
- `PodSummary.pool` — registry metadata for both pools
- Envoy API protos under `server/proto/envoy/` — ext_authz compile deps
- `solution_documents` table/repo — template domain (not routing-critical)

## Out of scope (optional later)

- K8s login-pod pool reconciler / seed Job
- Second `login-pod` in Docker Compose
- Remove `solution_documents` domain entirely

## Verification

```bash
cd router.svc/server && uv run pytest -q
cd router.svc/client_py && uv run pytest -q
cd router.svc/client_ts && npm test
cd test_client_nextjs && npm run build
cd router.svc/server && ./tools/generate_protos.sh   # pool only after echo removed
cd router.svc/client_py && ./tools/generate_protos.sh
cd router.svc/client_ts && ./tools/generate_protos.sh
```

Local E2E: `./infra/docker/start-local.sh -r -s -d` → Next dev → login → lease → `/home`.

## Status

Phases 1–2 complete (2026-05-29).

## Phase 3 — Lease resume (done)

See **[LEASE_RESUME_PLAN.md](LEASE_RESUME_PLAN.md)** — `GetLease`, `already_leased`, web auto-resume, CLI `lease` command.

# router.svc

Routing control plane: **gRPC** API (Python), **ext_authz**, Postgres assignment store, reconciliation, and reaper.

| Path | Role |
|------|------|
| **`server/`** | `solutions_service` package, protos, `app_config.toml` |
| **`client_py/`** | Python `router-client` (grpc.aio) |
| **`client_ts/`** | TypeScript `@router/client-ts` (@grpc/grpc-js) |
| **`../pod_manager_cli/`** | Operator CLI (uses client) |

See **`server/README.md`**, **`client_py/README.md`**, **`client_ts/README.md`**, and **`docs/local-testing/`** for local testing.

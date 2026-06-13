# Repository layout

| Path | Role |
|------|------|
| `envoy/` | Envoy image and static config (ext_authz, dynamic forward proxy) |
| `router.svc/` | gRPC control plane, ext_authz, Postgres store |
| `pods/` | `login_pod` and `backend_pool_node` workload images |
| `infra/docker/` | Local Compose stack and scripts |
| `test_client_nextjs/` | Browser test UI (Next.js) |
| `pod_manager_cli/` | Operator CLI (gRPC) |
| `config/deploy/` | `local.env` / `aws.env` endpoint profiles |
| `dev_testing/` | Integration test runner (local + AWS) |
| `docs/` | Developer and DevOps guides (this tree) |

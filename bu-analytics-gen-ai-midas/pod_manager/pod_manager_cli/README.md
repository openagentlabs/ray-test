# pod_manager_cli

Operator console for the routing control plane. **gRPC only** to `router.svc` on port **8804**.

## Install

```bash
cd pod_manager_cli
uv sync
```

## Commands

```bash
export POD_MANAGER_HOST=localhost
export POD_MANAGER_PORT=8804

uv run pod-manager pool
uv run pod-manager claim --sub alice
uv run pod-manager route --sub alice --envoy-url http://localhost:10000
uv run pod-manager e2e --sub alice
uv run pod-manager config env
```

Optional HTTP smoke tests use `ENVOY_URL` (default `http://localhost:10000`). `route` and `e2e` hit `GET /api/v1/me` (JSON `backend_pool_node`) or HTML root for legacy checks.

Automated stack smoke tests: `./infra/docker/test-local.sh` (or `./infra/docker/start-local.sh -r -s -d -t`).

Full guide: [docs/local-testing/cli-operator.md](../docs/local-testing/cli-operator.md).

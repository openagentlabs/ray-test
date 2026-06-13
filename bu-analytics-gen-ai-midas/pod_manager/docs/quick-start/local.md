# Local quick start

Day-to-day development on your machine. Endpoint variables for CLI and clients are in [`config/deploy/local.env`](../../config/deploy/local.env).

**Prerequisites:** Docker, [uv](https://docs.astral.sh/uv/), Node.js 20+. The stack runs a local Postgres container; `router.svc` creates its `pm_*` tables automatically at startup.

## 1. Start the stack

Repository root — [▶ Run](command:workbench.action.tasks.runTask?%5B%22qs-local-stack%22%5D)

`-r` resets data; `-s` start; `-d` detached; `-t` runs smoke tests when healthy.

```bash
./infra/docker/start-local.sh -r -s -d -t
```

## 2. Load the local profile

[▶ Run](command:workbench.action.tasks.runTask?%5B%22qs-local-profile%22%5D)

```bash
source config/deploy/local.env
cd pod_manager_cli && uv sync
```

## 3. Optional — three-terminal layout

| Terminal | Run | Purpose |
|----------|-----|---------|
| 1 | [▶ Stack (no auto-test)](command:workbench.action.tasks.runTask?%5B%22qs-local-stack-no-test%22%5D) | Stack only |
| 2 | [▶ Profile + CLI deps](command:workbench.action.tasks.runTask?%5B%22qs-local-profile%22%5D) then run `pod-manager` commands in that terminal | gRPC / HTTP smoke |
| 3 | [▶ Web test client](command:workbench.action.tasks.runTask?%5B%22qs-local-web%22%5D) | Browser UI at http://localhost:3000 |

## 4. Smoke checks

| Step | Run |
|------|-----|
| Docker smoke script | [▶ Run](command:workbench.action.tasks.runTask?%5B%22qs-local-test-local%22%5D) |
| Pool status | [▶ Run](command:workbench.action.tasks.runTask?%5B%22qs-local-pool%22%5D) |
| E2E (`alice@example.com`) | [▶ Run](command:workbench.action.tasks.runTask?%5B%22qs-local-e2e%22%5D) |
| Unified `dev-test` | [▶ Run](command:workbench.action.tasks.runTask?%5B%22qs-local-dev-test%22%5D) |

```bash
source config/deploy/local.env
./infra/docker/test-local.sh
cd pod_manager_cli && uv run pod-manager pool
cd pod_manager_cli && uv run pod-manager e2e --sub alice@example.com
cd dev_testing && uv sync && uv run dev-test all --target local
```

## Next steps

- [local-testing/README.md](../local-testing/README.md) — ports, flows
- [local-testing/web-test-client.md](../local-testing/web-test-client.md) — browser UI
- [local-testing/three-terminal-setup.md](../local-testing/three-terminal-setup.md) — env vars and startup order

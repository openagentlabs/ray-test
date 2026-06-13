# Pool workload pods

HTTP workloads registered in Postgres and reached through Envoy dynamic forward proxy.

| Directory | Pool | Role |
|-----------|------|------|
| **`backend_pool_node/`** | `backend_pool` | Exclusive per-user backend after `AcquireLease` |
| **`login_pod/`** | `login_pod_pool` | Shared login service when user has no lease |

## Local (Docker Compose)

Built from `infra/docker/docker-compose.local.yml`:

```bash
# From repo root
docker build -t backend-pool-node:local ./pods/backend_pool_node
docker build -t login-pod:local ./pods/login_pod
```

Or use `./infra/docker/start-local.sh -s`.

## Kubernetes

- Backend: `pods/backend_pool_node/k8s/statefulset.yaml`
- Login: Helm `infra/helm/routing-tier` (`loginPod` Deployment/Service)

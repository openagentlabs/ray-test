# login_pod

Shared **login pool** workload for users without a backend lease. Traffic is load-balanced across replicas; pods do not hold exclusive user assignments.

## API

- `POST /login` — JSON `{ "user_name", "user_password" }` (email + password; password not verified yet).
- Sets HttpOnly cookie `pod_manager_user` (email) on success.
- `GET /healthz`
- `/api/*` — returns **403** JSON `{ "error": "no_backend_lease", ... }` when Envoy routes unleased users here.

## Run locally

```bash
# From repo root
docker build -t login-pod:local ./pods/login_pod
docker run --rm -p 8080:8080 login-pod:local
```

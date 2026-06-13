# MIDAS Docker images (`deploy/ecs-app/docker`)

Container build contexts for MIDAS services. Images are built in **`Jenkinsfile_Deploy_App`** and pushed to **Amazon ECR** repositories defined in Terraform ([`ecr.tf`](../ecr.tf)).

- **Build matrix (single source of truth):** [`build-registry/images.yaml`](build-registry/images.yaml) - see [`build-registry/README.md`](build-registry/README.md) for field definitions.
- **Solution doc index:** [Solution documentation index](../../../README.midas.md)

## v1 services

| Logical name | Context directory | ECR suffix (`midas-{env}-…`) |
|--------------|--------------------|------------------------------|
| `midas-web-frontend-svc` | [`midas-web-frontend-svc/`](midas-web-frontend-svc/) | `midas-web-frontend-svc` (nginx stub includes **`/health`** for Kubernetes probes) |
| `midas-api-backend-svc` | [`midas-api-backend-svc/`](midas-api-backend-svc/) | `midas-api-backend-svc` |
| `midas-graph-svc` | [`midas-graph-svc/`](midas-graph-svc/) | `midas-graph-svc` |

## Add a new image

1. Add a subdirectory with a **`Dockerfile`** (and optional `.dockerignore`).
2. Add a row to [`build-registry/images.yaml`](build-registry/images.yaml).
3. Add an **`module`** for a dedicated ECR repository in [`ecr.tf`](../ecr.tf) if the service needs its own repo (same pattern as existing services).
4. Update Helm values/charts under [`../helm/`](../helm/) and [`../helm/releases.yaml`](../helm/releases.yaml) as needed.
5. Refresh **[`README.midas.md`](../../../README.midas.md)** (the long-form MIDAS overview; the repo root `README.md` is the Atlas landing page) if you add a new first-class README.

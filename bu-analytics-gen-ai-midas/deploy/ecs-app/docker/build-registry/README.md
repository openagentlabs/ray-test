# Build registry (`images.yaml`)

Machine-readable list of Docker images the pipeline builds and pushes to ECR.

## Fields (`version: 1`)

| Field | Required | Description |
|-------|----------|-------------|
| `service` | yes | Directory name / logical service id (matches Terraform `repository_name_suffix` for ECR). |
| `context` | yes | Path to build context, repo-relative (e.g. `deploy/ecs-app/docker/midas-web-frontend-svc`). |
| `dockerfile` | yes | Dockerfile name inside the context (usually `Dockerfile`). |
| `ecr_repository_suffix` | yes | Suffix after `midas-{environment}-` for the ECR repository name. |

## CI

- Parsed by **`deploy/scripts/ci/docker-build-matrix.sh`** using **`yq`** (installed on the fly if missing).
- Jenkins runs this script from the repo checkout root after **`terraform output`** supplies registry URLs.

## Solution doc index

See [Solution documentation index](../../../../README.midas.md).

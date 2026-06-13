# dev_testing

Unified **local** and **AWS** integration tests for the pod_manager routing tier.

## Setup

```bash
cd dev_testing
uv sync
```

## Usage

```bash
# Local stack must be running: ./infra/docker/start-local.sh -s
uv run dev-test health --target local
uv run dev-test all --target local

# After AWS deploy and write-aws-profile.sh:
source ../config/deploy/aws.env
uv run dev-test all --target aws
```

## Modules

| Command | Purpose |
|---------|---------|
| `health` | Envoy `/healthz` and traffic listener |
| `postgres` | Table existence (+ local seed check) |
| `grpc-pool` | `GetPoolStatus` |
| `grpc-lease` | Acquire / Get / Release lease |
| `http-login` | `POST /login` via Envoy |
| `http-routing` | Unleased 403 and leased 200 on `/api/v1/me` |
| `integration` | Full E2E including sticky routing |
| `all` | Run all modules in order |

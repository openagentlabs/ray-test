# IAM (`iam.svc`)

Identity and access for the Ray Test platform: authentication, users, logins, RBAC, invites, and JWT-based browser auth. Domain logic runs in a Python gRPC server backed by DynamoDB; browser apps call the HTTP auth API via `@arb/http-auth-client`.

<div align="left">

<small>

| | |
|:--|:--|
| **Version** | 0.1.0 |
| **Dev gRPC port** | 8803 |
| **Dev HTTP auth port** | 8873 |

</small>

</div>

---

## 1. Purpose

`iam.svc` is the **identity and access** bounded context for the monorepo. It owns:

- User, login, and session persistence (DynamoDB)
- User types, login types, skills, and invites
- RBAC (roles, permissions, assignments)
- JWT issuance, refresh, and validation for browser clients (FastAPI HTTP auth API)
- gRPC APIs for service-to-service callers (`IamService` in `proto/iam/v1/iam.proto`)

Call IAM for any feature involving users, credentials, tokens, roles, or permissions shared across platform services — not duplicate identity storage in `frontend/` or other `*.svc/` trees.

---

## 2. When to use it

| Need | Use |
|------|-----|
| Browser login, refresh, logout, token validation | `iam.svc/http-auth-client` (`@arb/http-auth-client`) against the HTTP auth API |
| Domain rules, persistence, auth decisions | Extend `iam.svc/server` — never `frontend/` or presentation handlers |
| Service-to-service IAM over gRPC | Call `iam.svc/server` gRPC directly from other `*.svc/` servers (port **8803**) |

Canonical dev ports are defined in **`.cursor/rules/solution/solution.mdc`** (gRPC **8803**; HTTP auth **8873** in `server/app_config.toml`).

---

## 3. Layout

| Path | Package | Role |
|------|---------|------|
| `server/` | `iam-service` (Python, uv) | gRPC + HTTP auth server, DynamoDB repositories, protobuf source (`proto/`) |
| `http-auth-client/` | `@arb/http-auth-client` | Zod schemas + HTTP client for login, refresh, JWKS, token validation |

Each package has its own **`README.md`**. Server implementation detail, protobuf regeneration, and database reset: **`server/README.md`**.

---

## 4. Run locally

### Server (gRPC + HTTP auth)

From `iam.svc/server`:

```bash
uv sync --dev
IAM_APP_CONFIG_PATH=app_config.toml uv run iam-service
```

- gRPC listens on **8803** (`[api_service]` in `app_config.toml`).
- HTTP auth listens on **8873** when `[http_auth] enabled = true`.
- Copy `server/.env.example` to `server/.env.local` for bootstrap identity (`IAM_BOOTSTRAP_*`) and local overrides.
- DynamoDB table names in `app_config.toml` mirror Terraform outputs — configure `[dynamodb.tables]` after `infra/aws_tf` apply.

### HTTP auth client

```bash
cd iam.svc/http-auth-client && npm install && npm run build
```

### Tests

```bash
cd iam.svc/server && uv run pytest
cd iam.svc/http-auth-client && npm test
```

See **§7 Testing** below for framework, layout, and run patterns. Individual test names are not listed here — they change often.

---

## 5. Quick reference

| Surface | Port | Client |
|---|---:|---|
| gRPC `IamService` | 8803 | Other `*.svc/` servers (no TypeScript client in this repo) |
| HTTP auth API | 8873 | `@arb/http-auth-client` |

---

## 6. Architecture (Clean / Ports and Adapters)

| Layer | Path | Naming | Depends on |
|---|---|---|---|
| **Domain** | `server/src/iam_service/domain/` | Entities: `User`, `Login`, `Invite` | Nothing external |
| **Ports** | `server/src/iam_service/repositories/ports/` | Protocols: `UserPort`, `LoginPort` | Domain + `Result` |
| **Services** | `server/src/iam_service/services/` | `*Application`, `*Service` | Ports, domain |
| **Adapters** | `server/src/iam_service/database/repositories/` | `*Repository` | aioboto3, records |
| **Delivery** | `grpc_transport/`, `http_transport/` | `IamGrpcServicer`, `routes.py` | Services only |
| **Plugins** | `plugins/vault/`, `plugins/idp/` | `*Driver` + `*Port` interface | IoC via `core/container.py` |
| **Core** | `core/app_config_store.py`, `core/container.py` | Singleton `app_config()`, `ServiceContainer` | TOML once at startup |

**Config singleton:** `init_app_config()` loads `app_config.toml` once at startup; `app_config()` returns the cached instance everywhere — no reference passing.

**IoC:** `ServiceContainer.build()` wires repositories, plugin drivers, and applications from the singleton config. Justified for plugin substitution (vault, IdP) and composition-root growth.

**Errors:** `returns` `Result[T, AppError]` at boundaries (Rust-style explicit errors, not opaque exceptions).

---

## 7. Testing

Python server tests live under `iam.svc/server/tests/`:

| Folder | Purpose |
|---|---|
| `unit/` | Isolated logic, validation, singleton, container, mocks |
| `integration/` | gRPC servicer and HTTP auth wiring |
| `database/` | Repository and pagination semantics |
| `support/` | Pytest plugins (e.g. agent result table) |

**Framework:** pytest (mandatory repo standard). Run `uv sync --dev && uv run pytest` from `server/`.

We do not list individual tests in this README. For layout rules, user-case coverage, traffic-light agent tables, and the single-test pattern, see **`.cursor/rules/testing_py/testing_py.mdc`**.

---

## 8. Configuration and observability

| File | Role |
|------|------|
| `server/app_config.toml` | Service ports, DynamoDB tables, vault/idp drivers, observability |
| `server/.env.local` | Bootstrap admin email/password and process env overrides |
| `server/Dockerfile` | Canonical container image (see `infra/aws/containers/`) |

`iam.svc/server` is the reference integration for **`lib/exl-observability`** — see **`doc/observibility/observability-guide.md`**.

### Reset dev database

With the server running, call the gRPC `ResetDatabase` RPC (dev credentials in `server/.env.example`) or use the repo reset helper when available. See **`server/README.md`** for `ResetDatabase` behavior, bootstrap env vars, and reset workflow.

---

## 12. Related

| Topic | Path |
|-------|------|
| Monorepo layout and dev ports | `.cursor/rules/solution/solution.mdc` |
| Server runbook (proto, reset) | `iam.svc/server/README.md` |
| Observability guide | `doc/observibility/observability-guide.md` |
| Python / async gRPC policy | `.cursor/rules/python/python.mdc` |
| TypeScript gRPC clients | `.cursor/rules/typescript/typescript.mdc` |
| Local Docker compose (IAM image) | `infra/aws/local-docker-compose/README.md` |
| EXL Observability library | `lib/exl-observability/README.md` |

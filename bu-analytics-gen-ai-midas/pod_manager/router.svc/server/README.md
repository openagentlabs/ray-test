# solutions.svc — Python gRPC server

Async **`grpc.aio`** server with `returns` **`Result`** types, structured logging, and per-RPC handler objects.

## Layout

- Run and install from **`server/`** (this directory).
- Python gRPC client for **`PodManagerService`** lives in **`../client_py/`**.
- TypeScript gRPC client lives in **`../client_ts/`**.

## Setup

```bash
cd solutions.svc/server
python3 -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
```

## Regenerate protobuf (Python)

After editing `proto/**/*.proto`:

```bash
cd solutions.svc/server
python -m grpc_tools.protoc \
  -I proto \
  --python_out=src \
  --grpc_python_out=src \
  --pyi_out=src \
  proto/solutions/v1/echo.proto
```

Generated modules live under `src/solutions/v1/` (importable as `solutions.v1`).

## Run

```bash
cd solutions.svc/server
. .venv/bin/activate
solutions-service
```

Default bind: `api_service.host` / `api_service.port` in `app_config.toml`.

## Configuration overrides

Every leaf in **`app_config.toml`** can be overridden by environment variables (container inject or local **`.env`**).

1. Copy **`server/.env.example`** → **`server/.env`** (gitignored).
2. On startup, `.env` then `.env.local` are loaded from the directory containing the config file, then env vars are merged into TOML (see **`solutions_service/core/config_env.py`**).
3. **Canonical** names: `POD_MANAGER_<SECTION>_<FIELD>` (e.g. `POD_MANAGER_POSTGRES_TABLE_PREFIX`).
4. **Legacy** names (`SOLUTIONS_SERVICE_GRPC_PORT`, `LOG_LEVEL`, etc.) remain supported.

## Postgres

- Routing-tier state lives in the **shared backend Postgres** (RDS), in a **dedicated schema** (default `pod_manager`). The service connects via `asyncpg` using a connection pool (`PostgresContext`) whose `search_path` is pinned to that schema, and bootstraps the schema and its tables at startup with `CREATE SCHEMA IF NOT EXISTS` + `CREATE TABLE IF NOT EXISTS`.
- The dedicated schema (plus the `pm_` table prefix) keeps the routing tier isolated from backend-owned tables (e.g. `public.message_states`): `pod_manager.pm_backend_pool`, `pm_login_pod_pool`, `pm_user_assignments`, `pm_assignment_events`, `pm_solution_documents`, `pm_service_config`.
- Configure **`[postgres]`** in **`app_config.toml`**: `dsn` (or the `DATABASE_URL` env alias — the same variable the backend uses), `schema_name`, `table_prefix`, `pool_min`/`pool_max`, `command_timeout_sec`. See `AppConfig.physical_table`. The DB role needs `CREATE` on the database for first-run schema creation (or pre-create the `pod_manager` schema).

## Checks

```bash
cd solutions.svc/server
ruff check src tools
mypy src/solutions_service
pytest
```

# EXLdecision.AI

## Transform Your Data into Actionable Intelligence

The most comprehensive analytics platform with AI-powered insights, synthetic data generation, and advanced modeling capabilities designed for modern businesses.

<div align="left">

<small>

| | |
|:--|:--|
| **Version** | 1.0.0 |
| **Updated** | 2026-06-14 12:00 UTC |
| **Owner** | platform@example.com |

</small>

</div>

---

# EXL Observability — Cursor Agent Rules

Rules for implementing and maintaining observability in Python microservices using the **`exl-observability`** library (`lib/exl-observability/`).

---

## Library placement and packaging

| Rule | Requirement |
|------|-------------|
| **Library location** | All observability interfaces and drivers live in `lib/exl-observability/` — never embed driver code inside `*.svc/server/`. |
| **Package name** | PyPI/install name: `exl-observability`; import root: `exl_observability`. |
| **Self-contained** | Library has its own `pyproject.toml`, `uv.lock`, dependencies, and tests. |
| **Publishable** | Must be installable via `pip install exl-observability` or editable `uv` path dependency. |
| **Service dependency** | Microservices declare `exl-observability` in `pyproject.toml` with `[tool.uv.sources]` path for monorepo dev. |

---

## Five interfaces (mandatory separation)

| Interface | Module | Purpose | Separate from |
|-----------|--------|---------|---------------|
| **Application logging** | `exl_observability.logging` | General application/diagnostic logs | Security logging |
| **Security logging** | `exl_observability.security_logging` | Auth, access, privilege, audit events | Application logging |
| **Tracing** | `exl_observability.tracing` | Distributed request spans | Logging |
| **Metrics** | `exl_observability.metrics` | Counters, gauges, histograms, timers | Tracing |
| **APM** | `exl_observability.apm` | Transaction/performance events | Metrics |

### Interface design rules

1. Each interface defines a **driver protocol** (`*Driver`) with `async init()`, `async shutdown()`, `create_client()`, and hot-path emit/record methods.
2. Application code uses **clients only** (`LoggingClient`, `SecurityLoggingClient`, etc.) — never import CloudWatch/boto3 in service code.
3. **NoOp drivers** must exist for every interface; disabled config must route to NoOp (zero network, minimal CPU).
4. Drivers live in **separate modules** under `exl_observability/drivers/<driver_name>/`.
5. Security logging uses a **separate log group, stream prefix, config section, and client** — never mix with application logs.

---

## AWS CloudWatch drivers

| Driver | Path | Backend |
|--------|------|---------|
| Application logging | `drivers/cloudwatch_logging/` | CloudWatch Logs (`PutLogEvents`) |
| Security logging | `drivers/cloudwatch_security_logging/` | CloudWatch Logs (separate group) |
| Tracing | `drivers/cloudwatch_tracing/` | X-Ray segment documents (UDP daemon) |
| Metrics | `drivers/cloudwatch_metrics/` | CloudWatch Metrics (`PutMetricData`) |
| APM | `drivers/cloudwatch_apm/` | CloudWatch Logs (APM JSON channel) |

### Driver rules

1. All boto3/sync I/O runs inside `asyncio.to_thread()` — never block the event loop.
2. Hot-path calls enqueue to `AsyncExportQueue` — bounded queue; drop when full (protect latency).
3. Export failures must **never** raise into application code or recurse into logging.
4. Each driver reads config only from its **`[observability.drivers.<name>]`** TOML section.
5. `init()` creates streams/queues; `shutdown()` flushes and stops workers.

---

## Configuration (`app_config.toml`)

### Required sections

```toml
[observability.identity]
service_id = "..."
service_name = "..."
service_version = "..."
instance_id = "..."
environment = "dev"

[observability.logging]
enabled = true
driver = "cloudwatch"   # or "noop"
level = "DEBUG"

[observability.security_logging]
enabled = true
driver = "cloudwatch"
level = "INFO"

[observability.tracing]
enabled = false
driver = "cloudwatch"
sample_rate = 1.0

[observability.metrics]
enabled = false
driver = "cloudwatch"
namespace = "EXL/ServiceName"

[observability.apm]
enabled = false
driver = "cloudwatch"

[observability.drivers.cloudwatch_logging]
region = "us-east-1"
log_group_name = "/path/to/app/logs"
log_stream_prefix = "svc-name"
queue_max_size = 10000
```

### Config rules

1. Default application log level: **DEBUG**.
2. Interface `driver` field selects implementation: `"noop"` or `"cloudwatch"`.
3. Service `AppConfig` loads observability via `ObservabilityConfig.from_toml_tables()`.
4. Never hard-code AWS regions, log groups, or account IDs in service code — use `app_config.toml` or generated defaults files.
5. Link project constants via **`.cursor/rules/constants/constants.mdc`** for region/account references in docs only.

---

## Runtime lifecycle

| Phase | Call | When |
|-------|------|------|
| **Init** | `await ObservabilityRuntime(config).init()` | After `AppConfig.load()`, before serving traffic |
| **Use** | `get_logging_client()`, etc. | Anywhere in application after init |
| **Shutdown** | `await runtime.shutdown()` | On SIGINT/SIGTERM, after gRPC server close |

### Lifecycle rules

1. Single `ObservabilityRuntime` per process.
2. Attach stdlib bridge **after** runtime init: `attach_stdlib_bridge(level_name=...)`.
3. Pre-init client accessors return NoOp-bound clients (safe, zero impact).
4. Always call `shutdown()` on graceful exit.

---

## Log format standards

### Application logs (`exl-log-v1`)

```json
{
  "timestamp": "2026-06-14T12:00:00.000000+00:00",
  "level": "INFO",
  "message": "grpc_dispatch",
  "service": {"id":"...","name":"...","version":"...","instanceId":"...","environment":"dev"},
  "correlation_id": "uuid",
  "channel": "application",
  "attributes": {"method": "/iam.IamService/Ping"},
  "format": "exl-log-v1"
}
```

### Security logs (`exl-security-log-v1`)

Same structure; `channel: "security"`, `event_type` field (e.g. `auth_failure`, `access_denied`).

### APM events (`exl-apm-v1`)

`channel: "apm"`, `event_name`, optional `duration_ms`.

---

## Metrics factory rules

1. Metric types, groups, and names are **`StrEnum`** in `exl_observability.metrics.enums`.
2. Extend enums per service — do not use raw strings for metric identity.
3. `MetricsClient.new(type, name, group)` returns `Result[MetricHandle, ObsError]`.
4. `increment()`, `record()` validate type/value and return `Result`.
5. Services may add service-specific enums in a local module that re-exports/extends the base enums.

---

## Python code standards (mandatory)

| Standard | Requirement |
|----------|-------------|
| **PEP 8** | Enforced via Ruff in library and services |
| **Type hints** | Mandatory on all public functions and methods |
| **Async** | All driver `init`/`shutdown` and export paths are async |
| **Pydantic v2** | All configuration models |
| **Result types** | `returns` `Result`/`Success`/`Failure` at boundaries |
| **Separation of concerns** | Interfaces, clients, drivers, config, runtime in separate modules |
| **Complexity** | Keep modules focused; target observability score ≥ 8/10 |

---

## Microservice integration checklist

When wiring a new `*.svc/server/`:

- [ ] Add `exl-observability` to `pyproject.toml` dependencies
- [ ] Add `[observability.*]` sections to `app_config.toml`
- [ ] Load `ObservabilityConfig` in `AppConfig`
- [ ] Call `configure_observability()` in `main.py` before gRPC start
- [ ] Call `shutdown_observability()` on process exit
- [ ] Use `get_security_logging_client()` for auth/audit events
- [ ] Use correlation helpers from `exl_observability.core.correlation`
- [ ] Do **not** add OpenTelemetry/boto3 logging directly in service code

---

## Reference implementation

**`iam.svc/server/`** is the reference integration:

- Config: `iam.svc/server/app_config.toml`
- Bootstrap: `iam_service/core/observability_config.py`
- Entry: `iam_service/main.py`
- Client accessors: `iam_service/observability/__init__.py`

---

## Related documentation

| Document | Path |
|----------|------|
| Developer guide | [observability-guide.md](observability-guide.md) |
| Library README | `lib/exl-observability/README.md` |
| Solution ports | `.cursor/rules/solution/solution.mdc` |
| Python conventions | `.cursor/rules/python/python.mdc` |
| Error handling | `.cursor/rules/error/error.mdc` |

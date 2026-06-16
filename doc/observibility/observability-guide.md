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

# EXL Observability — Developer Guide

A practical guide to logging, security logging, tracing, metrics, and APM in Ray Test Python microservices using **`exl-observability`**.

---

## 1. What is exl-observability?

`exl-observability` is a **standalone Python library** at `lib/exl-observability/`. It gives every microservice the same five observability channels:

| Channel | What you log/measure | Example |
|---------|---------------------|---------|
| **Application logging** | Normal service events | "User listed", "DB query slow" |
| **Security logging** | Auth and audit events | "Sign-in failed", "Role changed" |
| **Tracing** | Request spans across calls | gRPC handler duration |
| **Metrics** | Numeric counters/gauges | `request_count`, `error_count` |
| **APM** | Performance transactions | "SignIn took 42ms" |

You write code against **clients**. The **driver** (CloudWatch, NoOp) is chosen at startup from `app_config.toml` — your business code never imports boto3 for observability.

---

## 2. Architecture (how it fits together)

```
app_config.toml
       │
       ▼
ObservabilityConfig  ──►  ObservabilityRuntime.init()
       │                         │
       │                         ├── LoggingDriver (cloudwatch | noop)
       │                         ├── SecurityLoggingDriver
       │                         ├── TracingDriver
       │                         ├── MetricsDriver
       │                         └── ApmDriver
       │
       ▼
Global clients: get_logging_client(), get_security_logging_client(), ...
       │
       ▼
Your service code (gRPC handlers, repositories, etc.)
```

**Golden rule:** Calling a client on the hot path should be **fast**. Disabled or NoOp drivers do almost nothing. Enabled drivers enqueue work to a background async queue — your RPC does not wait for CloudWatch.

---

## 3. Installation

### Inside this monorepo

```bash
cd lib/exl-observability
uv sync
uv pip install -e .
```

### In a microservice `pyproject.toml`

```toml
dependencies = [
  "exl-observability>=0.1.0",
]

[tool.uv.sources]
exl-observability = { path = "../../lib/exl-observability", editable = true }
```

Then:

```bash
cd your.svc/server
uv sync
```

### Published install (when available on your package index)

```bash
pip install exl-observability
```

---

## 4. Configuration

All settings live in the service **`app_config.toml`**. Example from `iam.svc`:

### Service identity (attached to every record)

```toml
[observability.identity]
service_id = "arb-iam-svc"
service_name = "arb-iam-svc"
service_version = "0.1.0"
instance_id = "local"
environment = "dev"
```

### Application logging

```toml
[observability.logging]
enabled = true
driver = "cloudwatch"    # "noop" for local dev with zero export
level = "DEBUG"          # Minimum level exported
```

### Security logging (separate channel)

```toml
[observability.security_logging]
enabled = true
driver = "cloudwatch"
level = "INFO"
```

### Tracing, metrics, APM

```toml
[observability.tracing]
enabled = false
driver = "cloudwatch"
sample_rate = 1.0

[observability.metrics]
enabled = false
driver = "cloudwatch"
namespace = "EXL/IAM"

[observability.apm]
enabled = false
driver = "cloudwatch"
```

### Driver-specific settings

```toml
[observability.drivers.cloudwatch_logging]
region = "us-east-1"
log_group_name = "/arb/arb_ai_assistant/services/iam_svc"
log_stream_prefix = "iam-svc"
queue_max_size = 10000

[observability.drivers.cloudwatch_security_logging]
region = "us-east-1"
log_group_name = "/arb/arb_ai_assistant/security/iam_svc"
log_stream_prefix = "iam-security"
queue_max_size = 5000
```

| Property | Meaning |
|----------|---------|
| `enabled` | Turn the interface on/off |
| `driver` | `"noop"` or `"cloudwatch"` |
| `level` | Minimum log level (logging interfaces only) |
| `log_group_name` | CloudWatch log group (must exist in AWS/Terraform) |
| `log_stream_prefix` | Prefix for per-process streams |
| `queue_max_size` | Max queued events before drop (protects latency) |
| `namespace` | CloudWatch metrics namespace |

---

## 5. Startup and shutdown

### Startup (in `main.py`)

```python
from iam_service.core.app_config import AppConfig
from iam_service.core.observability_config import configure_observability

loaded = AppConfig.load(config_path)
app_config = loaded.unwrap()

await configure_observability(config=app_config.observability)
# ... start gRPC server ...
```

`configure_observability`:

1. Builds `ObservabilityRuntime` from config
2. Calls `init()` on all five drivers
3. Attaches the stdlib logging bridge (existing `logging.getLogger()` calls still work)

### Shutdown

```python
from iam_service.core.observability_config import shutdown_observability

await server.close()
await shutdown_observability()
```

Always shut down observability **after** stopping traffic so queues flush.

---

## 6. Application logging

### Direct client usage

```python
from exl_observability.runtime import get_logging_client

log = get_logging_client()

log.info("user_created", user_id="u-123", actor="admin")
log.warning("slow_query", table="users", duration_ms=850)
log.error("dynamo_failure", error_code="ProvisionedThroughputExceeded")
```

### Stdlib logging (bridge)

Existing code using `logging.getLogger(__name__)` continues to work after `configure_observability()` — records are forwarded to the EXL client.

```python
import logging

logger = logging.getLogger(__name__)
logger.info("grpc_dispatch method=%s", "/iam.IamService/Ping")
```

### Log format (`exl-log-v1`)

Every application log line is JSON:

```json
{
  "timestamp": "2026-06-14T12:00:00.000000+00:00",
  "level": "INFO",
  "message": "user_created",
  "service": {
    "id": "arb-iam-svc",
    "name": "arb-iam-svc",
    "version": "0.1.0",
    "instanceId": "local",
    "environment": "dev"
  },
  "correlation_id": "550e8400-e29b-41d4-a716-446655440000",
  "channel": "application",
  "attributes": {"user_id": "u-123", "actor": "admin"},
  "format": "exl-log-v1"
}
```

**Parsing tip:** Filter on `format`, `channel`, `level`, `service.name`, and `correlation_id`.

---

## 7. Security logging

Security events use a **separate client and CloudWatch log group** — never `get_logging_client()` for audit trails.

```python
from exl_observability.runtime import get_security_logging_client

sec = get_security_logging_client()

sec.auth_failure("invalid_password", user_id="u-123", source_ip="10.0.0.5")
sec.auth_success("sign_in_ok", user_id="u-123", method="password")
sec.access_denied("missing_permission", user_id="u-123", permission="users:delete")
sec.privilege_change("role_assigned", user_id="u-123", role="admin")
sec.security_event("custom_event", "description", detail="...")
```

Format: `exl-security-log-v1` with `event_type` and `channel: "security"`.

---

## 8. Tracing

```python
from exl_observability.runtime import get_tracing_client

trace = get_tracing_client()

span = trace.start_span("SignIn", user_id="u-123")
try:
    # ... business logic ...
    trace.end_span(span)
except Exception:
    trace.end_span(span, error=True)
    raise
```

When `enabled = false`, spans are created in-memory only (no export). When enabled with `driver = "cloudwatch"`, segments are sent to the X-Ray daemon on `127.0.0.1:2000`.

---

## 9. Metrics (factory pattern)

Metrics use **enums** — not free-form strings.

```python
from exl_observability.core.result import Failure, Success
from exl_observability.metrics.enums import MetricGroup, MetricName, MetricType
from exl_observability.runtime import get_metrics_client

metrics = get_metrics_client()

created = metrics.new(
    MetricType.COUNTER,
    MetricName.REQUEST_COUNT,
    MetricGroup.GRPC,
)
if isinstance(created, Failure):
    err = created.failure()
    # handle err.message, err.code, err.detail
    raise RuntimeError(err.message)

handle = created.unwrap()
metrics.increment(handle)

duration = metrics.new(
    MetricType.HISTOGRAM,
    MetricName.REQUEST_DURATION_MS,
    MetricGroup.GRPC,
)
if isinstance(duration, Success):
    metrics.record(duration.unwrap(), 42.5)
```

### Extending enums for your service

Add values to `MetricName` / `MetricGroup` in the library, or define service-local enums that follow the same `StrEnum` pattern and contribute names via PR to `exl-observability`.

---

## 10. APM

```python
from exl_observability.runtime import get_apm_client

apm = get_apm_client()

apm.record_transaction("SignIn", duration_ms=42.0, user_id="u-123")
apm.record_event("cold_start_complete", component="main")
```

Format: `exl-apm-v1` JSON in a dedicated CloudWatch log group.

---

## 11. Correlation IDs

Correlation ties logs, security events, traces, and APM to one request.

```python
from exl_observability.core.correlation import (
    CORRELATION_METADATA_KEY,
    new_correlation_token,
    reset_correlation_token,
)

# In gRPC servicer (from metadata):
token, cid = new_correlation_token(metadata.get("x-correlation-id"))
try:
    # ... handle RPC ...
    pass
finally:
    reset_correlation_token(token)
```

All clients automatically include `correlation_id` in exported records.

---

## 12. Using the library outside an application

`exl-observability` is designed for **standalone use** in scripts, CLIs, or new microservices:

```python
import asyncio
from exl_observability.config import ObservabilityConfig
from exl_observability.runtime import ObservabilityRuntime

async def main() -> None:
    config = ObservabilityConfig.defaults()
    runtime = ObservabilityRuntime(config)
    await runtime.init()

    runtime.logging_client().info("hello_from_script")
    await runtime.shutdown()

asyncio.run(main())
```

Load real config from TOML:

```python
import tomllib
from pathlib import Path
from exl_observability.config import ObservabilityConfig

raw = tomllib.loads(Path("app_config.toml").read_text())
config = ObservabilityConfig.from_toml_tables(raw)
```

---

## 13. Local development tips

| Goal | Config |
|------|--------|
| Zero CloudWatch traffic | Set all `driver = "noop"` or `enabled = false` |
| App logs only | Enable `[observability.logging]` with `driver = "cloudwatch"` |
| Debug logging noise | Set `level = "INFO"` or `"WARNING"` |

NoOp drivers: **no network calls**, enqueue returns immediately.

---

## 14. Troubleshooting

| Symptom | Check |
|---------|-------|
| No logs in CloudWatch | `enabled = true`, `driver = "cloudwatch"`, IAM permissions, log group exists |
| `ModuleNotFoundError: exl_observability` | Run `uv sync` in service; use `uv run python -m pytest` |
| Logs missing correlation_id | Ensure `new_correlation_token()` wraps the request |
| Metrics not appearing | `observability.metrics.enabled = true`, correct namespace |
| Init failure on startup | Read `detail` in `ObsError`; verify region and log group names |

---

## 15. Where to read more

| Resource | Path |
|----------|------|
| Agent rules | [observability-rules.md](observability-rules.md) |
| Library source | `lib/exl-observability/src/exl_observability/` |
| IAM reference integration | `iam.svc/server/` |
| Metric enums | `lib/exl-observability/src/exl_observability/metrics/enums.py` |
| Log format builder | `lib/exl-observability/src/exl_observability/logging/format.py` |

---

## 16. Quick copy-paste cheat sheet

```python
# Logging
from exl_observability.runtime import get_logging_client
get_logging_client().info("event_name", key="value")

# Security
from exl_observability.runtime import get_security_logging_client
get_security_logging_client().auth_failure("reason", user_id="x")

# Tracing
from exl_observability.runtime import get_tracing_client
span = get_tracing_client().start_span("OperationName")
get_tracing_client().end_span(span)

# Metrics
from exl_observability.metrics.enums import MetricGroup, MetricName, MetricType
from exl_observability.runtime import get_metrics_client
m = get_metrics_client()
h = m.new(MetricType.COUNTER, MetricName.ERROR_COUNT, MetricGroup.GRPC).unwrap()
m.increment(h)

# APM
from exl_observability.runtime import get_apm_client
get_apm_client().record_transaction("RpcName", duration_ms=12.5)
```

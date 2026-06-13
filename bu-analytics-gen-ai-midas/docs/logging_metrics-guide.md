# MIDAS Logging & Metrics Guide

**Audience:** Developers extending MIDAS application services (backend, graph, etc.).  
**Scope:** End-to-end paths for **logs** (stdout → Fluent Bit → CloudWatch Logs) and **metrics** (application → CloudWatch Metrics), the components involved, and practical recipes for new log lines and new metrics.

For a dense **environment-variable / Helm-key matrix** (including OTEL-related vars), see [`docs/observability-configuration.md`](observability-configuration.md). This guide focuses on **flow, ownership, and operations**.

---

## Table of contents

1. [Introduction](#introduction)
2. [Logging — end to end](#logging--end-to-end)
   - [Components](#logging-components)
   - [ASCII overview](#logging-ascii-overview)
   - [Stages in detail](#logging-stages-in-detail)
   - [JSON schema recap](#json-log-schema-recap)
3. [Metrics — end to end](#metrics--end-to-end)
   - [Components](#metrics-components)
   - [ASCII overview](#metrics-ascii-overview)
   - [Stages in detail](#metrics-stages-in-detail)
   - [Relationship to logs](#relationship-to-logs)
4. [How to add a new logging message](#how-to-add-a-new-logging-message)
5. [How to add a new metric](#how-to-add-a-new-metric)
6. [Infrastructure & operations](#infrastructure--operations)
7. [Related documents](#related-documents)

---

## Introduction

MIDAS separates **logs** and **custom metrics** deliberately:

| Signal | Mechanism | Destination | Purpose |
|--------|-----------|-------------|---------|
| **Logs** | Python `logging` → stdout JSON | CloudWatch **Logs** (`/midas/<env>/backend`) | Human-readable audit, debugging, structured events (`event` field) |
| **Custom metrics** | `boto3` `put_metric_data` (and optionally other paths) | CloudWatch **Metrics** (e.g. namespace `MIDAS/Training`) | Dashboards, alarms, SLO-style numeric signals |

Logs are **not** used to carry primary metric payloads for the training/heartbeat implementation; metrics use the CloudWatch API directly so they appear under **Metrics**, not only inside log queries.

Two operating modes for **log format**:

| Mode | When | Output |
|------|------|--------|
| **Text** (`LOG_FORMAT=text`) | Local development | ANSI-coloured lines |
| **JSON** (`LOG_FORMAT=json`) | Shared environments (dev / uat / prod) when Helm sets observability | One JSON object per line on stdout |

---

## Logging — end to end

### Logging components

| Layer | Component | Location / notes |
|-------|-----------|------------------|
| Application | `logging` stdlib, `JsonFormatter`, filters | `backend/app/core/logging_config.py` |
| Application | Logger factory | `get_logger(__name__)` → `midas.*` hierarchy |
| Application | Request correlation | `RequestContextFilter` + `contextvars` (middleware sets IDs) |
| Container | stdout / stderr | Kubernetes captures as container logs |
| Node | kubelet | Writes merged stream to host files under `/var/log/containers/` |
| Platform | Fluent Bit DaemonSet (`aws-for-fluent-bit`) | `kube-system`; tails files, enriches with k8s metadata |
| Platform | CloudWatch Logs output plugin | `cloudWatchLogs` (not legacy `cloudWatch`) |
| AWS | Log group | `/midas/<environment>/backend` (Terraform-owned) |
| IAM | EKS node role | `logs:PutLogEvents` on `/midas/*` (see `deploy/ecs-app/modules/eks/main.tf`) |

### Logging ASCII overview

```
+------------------------+     +---------------------------+
|  FastAPI / services    |     |  contextvars + middleware |
|  log.info(..., extra=  |---->|  RequestContextFilter      |
|    {"event": "..."})   |     |  (request_id, user_id, …)  |
+------------------------+     +-------------+-------------+
                                          |
                                          v
+------------------------+     +---------------------------+
|  logging_config.py     |     |  JsonFormatter (json) or   |
|  setup_logging()       |---->|  CustomFormatter (text)    |
+------------------------+     +-------------+-------------+
                                          |
                                          v
                               +---------------------------+
                               |  SafeStreamHandler        |
                               |  -> process stdout        |
                               +-------------+-------------+
                                             |
                                             v
+------------------------+     +---------------------------+
|  Kubernetes / kubelet  |     |  /var/log/containers/     |
|  container runtime     |---->|  *.log (per pod)        |
+------------------------+     +-------------+-------------+
                                             |
                                             v
+------------------------+     +---------------------------+
|  Fluent Bit DS         |     |  INPUT tail               |
|  (kube-system)         |---->|  FILTER kubernetes        |
|                        |     |  FILTER grep (midas-apps) |
|                        |     |  OUTPUT cloudWatchLogs      |
+------------------------+     +-------------+-------------+
                                             |
                                             v
                               +---------------------------+
                               |  Amazon CloudWatch Logs    |
                               |  Log group:                |
                               |  /midas/<env>/backend      |
                               |  Stream: pod/<tag>…       |
                               +---------------------------+
```

**Tag matching:** Fluent Bit matches real tail tags like `kube.var.log.containers.<pod>_<namespace>_<container>-<id>.log`. The Helm/Terraform values must use `cloudWatchLogs.match` compatible with that pattern (see `deploy/ecs-app/modules/observability-fluent-bit/main.tf`). A wrong match (e.g. `kube.midas-apps.*`) drops all records.

### Logging stages in detail

1. **Emit:** Application code calls `log.info("...", extra={"event": "my_event", ...})`. Always use `get_logger` from `app.core.logging_config`.
2. **Enrich:** `RequestContextFilter` adds correlation fields from contextvars when present.
3. **Format:** `JsonFormatter` emits a single-line JSON object with `timestamp`, `level`, `service`, `environment`, `logger`, `message`, `caller`, optional `@logGroupName`, and merged `extra`.
4. **Ship (container):** Handler writes to stdout; kubelet persists to node filesystem paths.
5. **Ship (Fluent Bit):** DaemonSet tails logs, runs kubernetes filter, **grep** keeps only namespace `midas-apps`, sends to the configured log group with stream prefix `pod/`.
6. **Query:** Operators use CloudWatch Logs Insights on `/midas/<env>/backend`; filter on `event`, `request_id`, etc.

### JSON log schema recap

Every JSON log line from `JsonFormatter` includes at least:

| Field | Always? | Description |
|-------|---------|-------------|
| `timestamp` | Yes | UTC ISO-8601, e.g. `2026-05-02T07:10:00.123Z` |
| `level` | Yes | `DEBUG` \| `INFO` \| `WARNING` \| `ERROR` \| `CRITICAL` |
| `service` | Yes | `LOG_SERVICE_NAME` (default `midas`) |
| `environment` | Yes | `LOG_ENVIRONMENT` (e.g. `dev`, `production`) |
| `logger` | Yes | Logger name, e.g. `midas.api.routes` |
| `message` | Yes | Log message string |
| `caller` | Yes | `{"file","line","function"}` |

Optional / contextual fields:

| Field | When | Description |
|-------|------|-------------|
| `@logGroupName` | `LOG_CLOUDWATCH_LOG_GROUP` set | CloudWatch log group — Insights joins |
| `event` | You pass in `extra` | Structured type: `http_request`, `llm_call`, `dataset_import`, … |
| `request_id`, `dataset_id`, `user_id`, `tenant_id`, `trace_id`, `span_id` | Request scope | Injected via `RequestContextFilter` from contextvars |
| `error` | Exceptions | `type`, `message`; `stackTrace` if `LOG_JSON_STACK_TRACE=true` |
| *(any)* | `extra={...}` | Merged into JSON; extras sorted alphabetically for stable diffs |

**Example (production JSON):**

```json
{"timestamp":"2026-05-02T07:10:00.123Z","level":"INFO","service":"midas-backend","environment":"development","@logGroupName":"/midas/dev/backend","event":"http_request","logger":"midas.api.routes","message":"POST /v1/query 200","caller":{"file":"routes.py","line":42,"function":"query"},"request_id":"abc-123","user_id":7,"duration_ms":143.5}
```

### Request correlation

`RequestContextFilter` reads Python `contextvars` so logs inside a request automatically include correlation IDs:

```python
# Middleware sets these at request entry:
set_request_id("abc-123")
set_user_context(user_id=7, tenant_id="acme")
set_trace_context(trace_id="...", span_id="...")

# Logs during the request pick these up without passing them into every call:
log.info("doing work", extra={"event": "query_start"})
```

---

## Metrics — end to end

### Metrics components

| Layer | Component | Location / notes |
|-------|-----------|------------------|
| Application | Training / heartbeat metric emission | `backend/app/services/keith_log_matrics_test.py` |
| Application | AWS SDK | `boto3.client("cloudwatch").put_metric_data` |
| Application | OpenTelemetry API/SDK | Meter setup (`opentelemetry-api`, `opentelemetry-sdk` in `requirements.txt`); export for heartbeat uses direct PutMetricData |
| Application | Optional EMF path | `backend/app/core/telemetry.py` — when enabled, uses **Embedded Metric Format** via `aws-embedded-metrics` (enable only if that dependency is installed and OTEL flags are on) |
| AWS API | `PutMetricData` | Namespace constrained by IAM condition (e.g. `MIDAS/Training`) |
| IAM | EKS worker node role | Inline policy `cloudwatch:PutMetricData` with namespace condition — see `deploy/ecs-app/eks-node-cloudwatch-metrics.tf` |
| Networking | VPC | MIDAS uses private subnets; CloudWatch regional endpoint / optional interface endpoint (`CLOUDWATCH_ENDPOINT_URL` in code if injected) |

### Metrics ASCII overview

```
+------------------------+     +---------------------------+
|  Application code      |     |  e.g. heartbeat thread    |
|  (training or startup) |---->|  random value / business    |
|                        |     |  statistic                |
+------------------------+     +-------------+-------------+
                                             |
                                             v
+------------------------+     +---------------------------+
|  keith_log_matrics_    |     |  _put_metric_direct()      |
|  test.py               |---->|  boto3 put_metric_data     |
+------------------------+     +-------------+-------------+
                                             |
                                             v
+------------------------+     +---------------------------+
|  IAM (node role)       |     |  Allow PutMetricData when   |
|                        |     |  cloudwatch:namespace =     |
|                        |     |  MIDAS/Training             |
+------------------------+     +-------------+-------------+
                                             |
                                             v
                               +---------------------------+
                               |  Amazon CloudWatch Metrics |
                               |  Namespace: MIDAS/Training |
                               |  Metric: keith_kets_*       |
                               |  Dimensions: operation,     |
                               |    service, environment     |
                               +---------------------------+
```

### Metrics stages in detail

1. **Emit:** Code calls `_put_metric_direct(operation=..., value=...)` (or your own wrapper) inside `keith_log_matrics_test.py` pattern.
2. **Namespace & metric name:** Example namespace `MIDAS/Training`, metric name `keith_kets_training_value`, dimensions `operation`, `service`, `environment`.
3. **Credentials:** Pod uses the **node instance profile** (same as Fluent Bit log path — no separate IRSA in current pattern). IAM must allow `cloudwatch:PutMetricData` for the intended namespace condition.
4. **Network:** `boto3` targets `monitoring.us-east-1.amazonaws.com` unless `CLOUDWATCH_ENDPOINT_URL` overrides for VPC endpoints.
5. **Consume:** CloudWatch console → Metrics → browse namespace; alarms in `deploy/ecs-app/cloudwatch-metrics.tf` etc.

### Relationship to logs

- **Same heartbeat, two channels:** `start_backend_heartbeat` logs an INFO line **and** calls `_put_metric_direct`. Logs remain in `/midas/<env>/backend`; metrics appear under **CloudWatch Metrics**.
- **Do not rely on Fluent Bit** to create custom metrics for this pattern — Fluent Bit ships **log lines**, not `PutMetricData`.

---

## How to add a new logging message

### Libraries (allowed)

| Use | Do not add |
|-----|------------|
| `logging` (stdlib) | `structlog`, `loguru`, `python-json-logger`, `print()` |
| `from app.core.logging_config import get_logger` | New logging packages to `requirements.txt` |
| Optional helpers in `logging_config.py` | Bypassing `get_logger` |

### Steps

1. **Import the logger helper**

   ```python
   from app.core.logging_config import get_logger

   log = get_logger(__name__)
   ```

2. **Choose a level** — `INFO` for normal lifecycle, `WARNING` / `ERROR` with `exc_info=True` for failures.

3. **Add structured `event` and extras**

   ```python
   log.info(
       "Payment reconciliation batch finished",
       extra={
           "event": "payment_reconcile_complete",
           "log_category": "finance",
           "batch_id": batch_id,
           "records_processed": n,
           "duration_ms": elapsed_ms,
       },
   )
   ```

4. **Exceptions**

   ```python
   try:
       ...
   except ValueError as exc:
       log.error("Invalid payload", exc_info=True, extra={"event": "payment_reconcile", "batch_id": batch_id})
       raise
   ```

5. **Reuse helpers** from `logging_config.py` when they fit:

   | Helper | Use |
   |--------|-----|
   | `log_dependency_event(log, dependency=..., operation=..., duration_ms=..., success=...)` | Outbound calls (DB, Redis, S3, HTTP, Bedrock) |
   | `DataQualityLogger` | Data lifecycle / ML ops with consistent phases |
   | `@log_execution_time("op_name")` | Auto-log duration for a function |
   | `hash_for_log(value)` | SHA-256 hex for correlation without raw PII |

6. **Bootstrap:** `setup_logging()` runs at import via `logging_config`; new standalone binaries should call `setup_logging()` once before logging.

7. **Verify locally** with `LOG_FORMAT=json` in `.env`; in cluster, confirm lines appear in `/midas/<env>/backend` after deploy.

### Configuration reference (logging)

All parameters are read from **environment variables** (no separate logging YAML). Local dev: `backend/.env`.

| Variable | Default | Values / notes |
|----------|---------|----------------|
| `LOG_LEVEL` | `INFO` | `DEBUG` \| `INFO` \| `WARNING` \| `ERROR` |
| `LOG_FORMAT` | `text` | `text` locally; **`json`** in shared envs — Helm sets this when `observability.enabled: true` |
| `LOG_FILE` | `logs/midas.log` | File path or `""` to disable file logging in containers |
| `ENABLE_CONSOLE_LOGGING` | `true` | Keep **`true`** in K8s — Fluent Bit reads stdout |
| `LOG_SERVICE_NAME` | `midas` | Per-service name, e.g. `midas-backend` |
| `LOG_ENVIRONMENT` | `ENVIRONMENT` / `ENV` / `development` | Shown as `environment` in JSON |
| `LOG_CLIENT_IP` | `false` | If `true`, may add hashed client IP to HTTP request logs |
| `LOG_JSON_STACK_TRACE` | `false` | Full `error.stackTrace` in JSON — dev only |
| `LOG_CLOUDWATCH_LOG_GROUP` | *(unset)* | Adds `@logGroupName`; Helm injects from `observability.logGroupName` |

**Helm:** `deploy/ecs-app/helm/midas-api-backend-svc/` — under `observability:` set `enabled`, `logGroupName`, `serviceName`, `environment`, etc.; templates map these to pod env vars.

---

## How to add a new metric

### Libraries involved today

| Package | Role |
|---------|------|
| `boto3` / `botocore` | `put_metric_data` to CloudWatch |
| `opentelemetry-api`, `opentelemetry-sdk` | Used in `keith_log_matrics_test.py` for meter/resource patterns; **direct** export uses boto3 |

Optional / separate path:

| Package | Role |
|---------|------|
| `aws-embedded-metrics` | Only if you use **EMF** via `telemetry.py` (`OTEL_ENABLED`, `OTEL_METRICS_ENABLED`) — confirm listed in `requirements.txt` before relying on it |

### Pattern A — Direct PutMetricData (recommended for custom namespace)

Aligned with `MIDAS/Training` and existing IAM:

1. Add a small function next to `_put_metric_direct` **or** factor a shared helper that builds `MetricData` entries with a **new metric name** and dimensions.
2. Keep namespace **`MIDAS/Training`** unless you change Terraform/IAM — the node policy scopes `PutMetricData` by namespace condition (`deploy/ecs-app/eks-node-cloudwatch-metrics.tf`).
3. Call your helper from the appropriate code path (service method, heartbeat, middleware).
4. Handle failures without breaking the caller:

   ```python
   try:
       client.put_metric_data(...)
   except Exception as exc:
       log.warning("PutMetricData failed (non-fatal): %s", exc)
   ```

5. Document new metric names and dimensions in `docs/observability-metric-catalog.md` if that file is maintained for your team.

### Pattern B — EMF via `telemetry.py`

If your environment installs `aws-embedded-metrics` and enables `OTEL_ENABLED` / `OTEL_METRICS_ENABLED`, follow `record_*` patterns in `backend/app/core/telemetry.py`. EMF writes **special JSON to stdout**; Fluent Bit / agents parse metrics from log pipeline — different from Pattern A.

### Pattern C — OTLP / AMP (Phase B)

When `OTEL_EXPORTER_OTLP_ENDPOINT` is set, `telemetry.py` can export metrics to a collector → Amazon Managed Prometheus. This is separate from the `MIDAS/Training` PutMetricData path.

### Operational rules

- **IAM:** Extending metrics beyond `MIDAS/Training` requires Terraform/IAM updates and Jenkins deploy — do not assume `PutMetricData` works for new namespaces without policy changes.
- **Release path:** Infrastructure changes go through the MIDAS Jenkins pipeline (`.cursor/rules/jenkins.mdc`), not laptop `terraform apply` against shared envs.

---

## Infrastructure & operations

| Concern | Where |
|---------|--------|
| Fluent Bit Helm module | `deploy/ecs-app/modules/observability-fluent-bit/main.tf` |
| Log group Terraform | `deploy/ecs-app/modules/observability-app-logs/` |
| Fluent Bit reference values (docs) | `deploy/observability/fluentbit/fluentbit-cloudwatch-values.yaml` |
| Enable Fluent Bit per env | `observability_fluent_bit_enabled` in `deploy/ecs-app/tfvars/*.tfvars` (e.g. `true` in `dev.tfvars`) |
| Node IAM for logs | `deploy/ecs-app/modules/eks/main.tf` (`node_cloudwatch_logs`) |
| Node IAM for metrics | `deploy/ecs-app/eks-node-cloudwatch-metrics.tf` |
| ECR mirror for Fluent Bit image | Private repo `midas-<env>-aws-for-fluent-bit` — nodes may have no public egress |

**Terraform → Helm (`aws-for-fluent-bit` chart):** the live plugin is **`cloudWatchLogs`** (not the legacy `cloudWatch` key). Important `set` values include:

| Helm value | Typical purpose |
|------------|-----------------|
| `cloudWatchLogs.enabled` | `true` — ship to CloudWatch Logs |
| `cloudWatchLogs.region` | `us-east-1` |
| `cloudWatchLogs.logGroupName` | `/midas/<env>/backend` |
| `cloudWatchLogs.logStreamPrefix` | `pod/` |
| `cloudWatchLogs.autoCreateGroup` | `false` — group owned by Terraform |
| `cloudWatchLogs.match` | Must match real tail tags, e.g. `kube.var.log.containers.*` |
| `additionalFilters` | Grep filter: namespace `midas-apps` only |
| `image.repository` | Private ECR mirror URL |

**MIDAS JSON parser (reference YAML):** optional `midas_json` parser for timestamp extraction — see `additionalParsers` in `fluentbit-cloudwatch-values.yaml`.

**Deploy:** use the MIDAS Jenkins pipeline (`.cursor/rules/jenkins.mdc`); do not `helm upgrade` / `terraform apply` to shared envs from a laptop.

```bash
# Example — trigger is via .cursor/tools/jenkins_tools.py with your job parameters
python3 .cursor/tools/jenkins_tools.py trigger --param ENVIRONMENT=dev  # plus required flags
```

---

## Related documents

| Document | Contents |
|----------|----------|
| `docs/observability-configuration.md` | Env vars, Helm keys, EMF-oriented architecture notes |
| `docs/observability-metric-catalog.md` | Metric catalog (if present / maintained) |
| `docs/adr/0001-midas-amp-amg-observability.md` | AMP / AMG direction |
| `.cursor/rules/logging/logging.mdc` | Agent/developer rules for Python logging |

---

## Appendix — configuration snippets (Helm)

Per-environment overlays under `deploy/ecs-app/helm/midas-api-backend-svc/` typically set:

```yaml
observability:
  enabled: true              # drives LOG_FORMAT=json and related env
  logGroupName: "/midas/dev/backend"
  serviceName: "midas-backend"
  environment: "dev"
```

Exact keys evolve with chart templates — verify `templates/deployment.yaml` for the authoritative env mapping.

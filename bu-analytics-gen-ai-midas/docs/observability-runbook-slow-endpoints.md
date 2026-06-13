# Slow-endpoint observability runbook

Use this runbook to find every API request that exceeds the
"any-handler-over-1-second-belongs-in-a-job" architecture rule
(`.cursor/rules/architecture.mdc`).

## What the backend emits

Every HTTP request goes through the timing middleware in
[`backend/main.py`](../backend/main.py). For each non-stream request the
middleware emits two structured log events:

| Event | Level | When |
|---|---|---|
| `http_request` | `INFO` (or `DEBUG` for `/`, `/health`) | Always |
| `slow_request` | `WARNING` | Only when `duration_ms > SLOW_REQUEST_THRESHOLD_MS` (default 1000 ms) |

Both events share the same field shape:

```json
{
  "event": "http_request",
  "log_category": "http",
  "method": "POST",
  "route": "/api/v1/insights/correlation-matrix",
  "path": "/api/v1/insights/correlation-matrix",
  "operation": "/api/v1/insights/correlation-matrix",
  "status_code": 200,
  "outcome": "success",
  "duration_ms": 14823.12,
  "is_slow": true,
  "slow_threshold_ms": 1000,
  "request_id": "8f3b...",
  "user_id": "<hashed>",
  "trace_id": "..."
}
```

`route` is the FastAPI **route template** (e.g.
`/api/v1/datasets/{dataset_id}/dqs`), not the rendered path. Aggregations
should always group on `route`, not `path`, otherwise every dataset gets
its own bucket.

## Configuration

| Env var | Default | Notes |
|---|---|---|
| `SLOW_REQUEST_THRESHOLD_MS` | `1000` | Emit a `slow_request` WARN log above this duration. Lower in dev for stricter SLOs. |
| `LOG_FORMAT` | `text` (dev) / `json` (Helm) | JSON is required for the queries below. |
| `LOG_LEVEL` | `INFO` | Must be `INFO` or finer to capture `http_request`; `WARNING` is enough for `slow_request`. |

Helm forces `LOG_FORMAT=json` in shared environments and ships every
container line to CloudWatch via Fluent Bit
(see `.cursor/rules/logging/logging.mdc`).

## CloudWatch Logs Insights queries

> Log group: `/midas/<env>/backend` (managed by Terraform).
> Run from **CloudWatch → Logs Insights** with the appropriate log group
> selected. Time range: pick the last 1 h / 24 h / 7 d as needed.

### 1. Top 25 slowest routes (p50 / p95 / p99 / count)

Authoritative answer for "which endpoints take more than 1 second?".

```
fields @timestamp, route, duration_ms, status_code, method
| filter event = "http_request"
| stats
    count() as requests,
    avg(duration_ms) as avg_ms,
    pct(duration_ms, 50) as p50_ms,
    pct(duration_ms, 95) as p95_ms,
    pct(duration_ms, 99) as p99_ms,
    max(duration_ms) as max_ms
  by route, method
| sort p95_ms desc
| limit 25
```

### 2. All routes whose p95 exceeds 1 second (refactor candidates)

```
fields @timestamp, route, duration_ms, method
| filter event = "http_request"
| stats
    count() as requests,
    pct(duration_ms, 95) as p95_ms,
    pct(duration_ms, 99) as p99_ms
  by route, method
| filter p95_ms > 1000
| sort p95_ms desc
```

After a release that moves heavy handlers to background jobs (for example insight routes returning `202` + poll), run queries **(1)** and **(2)** over the same **24-hour** window in dev (or the target environment) so the next refactor targets are chosen from measured p95, not estimates.

### 3. Slow request offenders by raw count (uses the dedicated WARN log)

Cheaper than (2) because it scans only `event=slow_request` rows.

```
fields @timestamp, route, duration_ms, status_code, method
| filter event = "slow_request"
| stats
    count() as slow_count,
    avg(duration_ms) as avg_ms,
    max(duration_ms) as max_ms
  by route, method
| sort slow_count desc
| limit 50
```

### 4. CPU-bound vs LLM-bound vs DB-bound — split by status code

```
fields @timestamp, route, duration_ms, status_code
| filter event = "slow_request"
| stats
    count() as slow_count,
    pct(duration_ms, 95) as p95_ms
  by route, status_code
| sort slow_count desc
```

A high `5xx` count alongside high `p95_ms` is usually an upstream
timeout (Bedrock, RDS) — fix the dependency. A high `2xx` count means
the handler genuinely runs that long and **should be a background job**.

### 5. Single offending request — pull the full story

```
fields @timestamp, level, message, event, duration_ms, request_id, route
| filter request_id = "8f3b...your-id-here..."
| sort @timestamp asc
```

`request_id` is auto-injected by `RequestContextFilter` on every log line
(`.cursor/rules/logging/logging.mdc` rule 7), so you can trace the full
call chain from the slow_request line back through every dependency
call (`event=dependency_call`) and LLM call (`event=llm_call`) the
handler made.

### 6. p95 latency timeline for one route (10-min buckets)

```
fields @timestamp, duration_ms
| filter event = "http_request" and route = "/api/v1/insights/correlation-matrix"
| stats pct(duration_ms, 95) as p95_ms, count() as requests by bin(10m)
| sort @timestamp asc
```

Useful for verifying that a refactor (sync → background job) actually
moved the p95 below the `slow_threshold_ms` line.

## Recommended CloudWatch alarm

Create a metric filter on the backend log group:

| Field | Value |
|---|---|
| Filter pattern | `{ $.event = "slow_request" }` |
| Metric namespace | `MIDAS/Http` |
| Metric name | `SlowRequestCount` |
| Dimension | `Route` (extracted from `$.route`) |
| Default value | `0` |

Then alarm: `SlowRequestCount > 10 over 5 minutes` per route — paged when
a previously-fast endpoint regresses.

## Shipping checklist for any new endpoint

Before merging a new endpoint, the author must answer:

1. What's the realistic p95 latency on a 4M-row dataset?
2. If it's > `SLOW_REQUEST_THRESHOLD_MS`, is the work in a background
   job (use `app.services.background_jobs.background_job_manager`)?
3. Is the handler stateless (no module-level dict storing job state,
   no `pd.DataFrame` cached only in pod RAM)?
4. Does the worker function acquire `dataset_job_lock` if it touches a
   shared `dataset_id`?

Failing any of these means the endpoint will show up in query (2) above
within hours of going to production.

## Related

- [`.cursor/rules/architecture.mdc`](../.cursor/rules/architecture.mdc) — "Stateless compute, managed state. Event-driven by default."
- [`.cursor/rules/logging/logging.mdc`](../.cursor/rules/logging/logging.mdc) — Log event taxonomy and required fields.
- [`docs/observability-kql-cookbook.md`](./observability-kql-cookbook.md) — Equivalent queries for OpenSearch Dashboards (Phase C).
- [`backend/app/services/background_jobs.py`](../backend/app/services/background_jobs.py) — Canonical background-job pattern (S3-mirrored, Celery/RQ-ready).
- [`backend/app/services/job_locks.py`](../backend/app/services/job_locks.py) — Per-dataset cross-process locks.

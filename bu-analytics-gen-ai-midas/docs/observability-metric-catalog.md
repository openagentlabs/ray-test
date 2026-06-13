# MIDAS Observability Metric Catalog

> All metrics below are emitted by `backend/app/core/telemetry.py`.
> Phase A metrics use the CloudWatch / EMF sink.
> Phase B metrics use the OTLP sink (OTel Collector → Amazon Managed Prometheus).
> See `docs/observability-configuration.md` for env var reference.

---

## HTTP Server Metrics (Phase A + B)

### `HttpRequestDuration` / `http.server.request.duration`

| Aspect | Value |
|---|---|
| CloudWatch name (EMF) | `HttpRequestDuration` |
| OTLP / Prometheus name | `http_server_request_duration_seconds` (histogram) |
| Unit | Milliseconds (EMF) / Seconds (OTLP) |
| Type | Histogram (EMF: single value per line; OTLP: full histogram) |
| EMF Namespace | `OTEL_METRICS_NAMESPACE` (default `MIDAS`) |
| Emitted when | `OTEL_ENABLED=true` and `OTEL_METRICS_ENABLED=true` (EMF) or `OTEL_EXPORTER_OTLP_ENDPOINT` set (OTLP) |

**Dimensions / Labels**

| Name | Values | Notes |
|---|---|---|
| `Service` | `OTEL_SERVICE_NAME` (default `midas-backend`) | All metrics carry this |
| `Environment` | `OTEL_ENVIRONMENT` (default from `APP_ENV`) | All metrics carry this |
| `Method` | `GET`, `POST`, `PUT`, `DELETE`, … | HTTP method |
| `Route` | `/api/v1/datasets/{dataset_id}/upload`, … | Templated (not raw path) |
| `Outcome` | `success`, `redirect`, `client_error`, `server_error`, `unknown` | Derived from status code |

**Properties (EMF only — high cardinality, not a CW dimension)**

| Name | Type | Notes |
|---|---|---|
| `StatusCode` | integer | Raw HTTP status code |

---

### `HttpRequestCount` / `http.server.request.count`

| Aspect | Value |
|---|---|
| CloudWatch name (EMF) | `HttpRequestCount` |
| OTLP / Prometheus name | `http_server_request_count_total` (counter) |
| Unit | Count |
| Type | Counter |

Same dimensions as `HttpRequestDuration`.

---

## LLM / Agent Metrics (Phase A — planned, not yet emitted)

The following metrics are the **intended next additions** in `telemetry.py`. They
follow the same pattern as the HTTP metrics and are documented here so dashboards
and alarms can be defined before the code is instrumented.

### `LlmCallDuration`

| Aspect | Value |
|---|---|
| CloudWatch name (EMF) | `LlmCallDuration` |
| OTLP / Prometheus name | `llm_call_duration_seconds` |
| Unit | Milliseconds (EMF) / Seconds (OTLP) |
| Dimensions | `Service`, `Environment`, `Model`, `Outcome` |

### `LlmPromptTokens` / `LlmCompletionTokens`

| Aspect | Value |
|---|---|
| CloudWatch names (EMF) | `LlmPromptTokens`, `LlmCompletionTokens` |
| OTLP names | `llm_prompt_tokens_total`, `llm_completion_tokens_total` |
| Unit | Count |
| Dimensions | `Service`, `Environment`, `Model` |

---

## CloudWatch Dashboard Widgets (Phase A)

Suggested widgets for a CloudWatch automatic dashboard on the `MIDAS` namespace:

| Widget | Metric(s) | Stat | Period |
|---|---|---|---|
| P50/P90/P99 request latency | `HttpRequestDuration` | p50, p90, p99 | 1 min |
| Request rate (rpm) | `HttpRequestCount` | Sum | 1 min |
| Error rate % | `HttpRequestCount` filtered by `Outcome=server_error` ÷ total | Sum | 5 min |
| 4xx client error rate | `HttpRequestCount` `Outcome=client_error` | Sum | 5 min |
| Latency heatmap by Route | `HttpRequestDuration` grouped by `Route` | p90 | 5 min |

---

## Prometheus / Grafana Panels (Phase B)

Once the ADOT Collector is deployed and metrics flow to AMP, use these PromQL
queries in Grafana:

```promql
# Request rate
rate(http_server_request_count_total{service_name="midas-backend"}[5m])

# P99 latency (histogram)
histogram_quantile(0.99, sum(rate(http_server_request_duration_seconds_bucket{service_name="midas-backend"}[5m])) by (le, route))

# Error rate %
sum(rate(http_server_request_count_total{midas_outcome="server_error"}[5m]))
  /
sum(rate(http_server_request_count_total{}[5m])) * 100
```

Full dashboard JSON: `deploy/observability/grafana/dashboards/midas-backend-overview.json`

---

## Adding a New Metric

1. Add a `record_<thing>(...)` function to `backend/app/core/telemetry.py`
   following the shape of `record_http_request`.
2. Add it to this catalog (EMF name, OTLP name, unit, dimensions).
3. Add a CloudWatch widget and/or Grafana panel definition above.
4. Call from the relevant code path.

No Helm or Terraform changes are needed for new metrics.

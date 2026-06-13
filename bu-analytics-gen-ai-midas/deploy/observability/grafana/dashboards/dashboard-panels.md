# Grafana Dashboard — MIDAS Backend Overview

Dashboard file: `midas-backend-overview.json`

## Data source

Amazon Managed Prometheus (AMP). The AMP query endpoint comes from the Terraform
output `amp_query_endpoint`. Configure it as a Prometheus data source in AMG.

## Panels

| Panel | Metric | Description |
|---|---|---|
| Request Rate (rpm) | `http_server_request_count_total` | Total requests per minute across all routes |
| Error Rate % | `http_server_request_count_total{midas_outcome="server_error"}` | 5xx rate as % of total |
| P99 Latency (ms) | `http_server_request_duration_seconds` histogram | 99th percentile end-to-end |
| P50 Latency (ms) | `http_server_request_duration_seconds` histogram | Median |
| Request Rate by Outcome | `http_server_request_count_total` grouped by `midas_outcome` | Shows success vs error breakdown |
| Latency Percentiles | `http_server_request_duration_seconds` P50/P90/P99 | All routes combined |
| P90 Latency by Route | `http_server_request_duration_seconds` grouped by `http_route` | Identify slow routes |

## Template variables

| Variable | Source | Description |
|---|---|---|
| `environment` | label_values on `deployment_environment` | Filter by env (dev / uat / prod) |
| `route` | label_values on `http_route` | Multi-select route filter |

## Import into AMG

1. In your AMG workspace, go to **Dashboards → Import**.
2. Upload `midas-backend-overview.json`.
3. Select your AMP workspace as the `Amazon Managed Prometheus` data source.

## Extending the dashboard

Add panels to the JSON file following the same structure. Reference
`docs/observability-metric-catalog.md` for PromQL queries.

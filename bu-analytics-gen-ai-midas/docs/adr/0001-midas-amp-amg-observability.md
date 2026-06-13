# ADR 0001 — MIDAS AMP + AMG Observability (Phase B)

| Field | Value |
|---|---|
| Status | Proposed |
| Date | 2026-05-01 |
| Author | MIDAS Platform Team |
| Affects layers | AI/ML, Platform/Infra, CI/CD |

---

## Context

MIDAS currently emits metrics via AWS Embedded Metric Format (EMF) to
CloudWatch Metrics (Phase A). EMF gives us the first metrics pipeline at zero
extra IAM cost, but CloudWatch dashboards have limited PromQL-style query
flexibility and no rich histogram bucket visualisation.

The team wants:
- Rich dashboards with Prometheus-native query language (PromQL) and histogram
  panels (latency percentile curves, heatmaps).
- A durable, Prometheus-compatible time-series store that supports alerting via
  Prometheus AlertManager or Grafana Alerting.
- Multi-source dashboards (backend app metrics + infrastructure metrics from
  CloudWatch + RDS Enhanced Monitoring in the same Grafana workspace).

---

## Decision

Deploy **Amazon Managed Service for Prometheus (AMP)** as the Prometheus-
compatible metric store and **Amazon Managed Grafana (AMG)** as the dashboarding
layer. The pipeline is:

```
EKS Pod (telemetry.py OTLP SDK)
  → ADOT OTel Collector DaemonSet (OTLP receiver, prometheusremotewrite exporter)
    → AMP workspace (private, VPC endpoint)
      → AMG workspace (data source: AMP + CloudWatch)
```

### Why AMP over self-managed Prometheus?

| Criterion | AMP | Self-managed Prometheus |
|---|---|---|
| Operational burden | Low (managed) | High (HA, storage, upgrades) |
| Private-by-default | Yes — VPC endpoint | Requires extra effort |
| PromQL compatible | Yes | Yes |
| Long-term retention | Configurable | Requires Thanos/Cortex |
| Jenkins/Terraform deploy | Yes | Yes |

### Why AMG over self-managed Grafana?

- Managed, SSO-ready (integrates with existing IAM Identity Center / Cognito).
- Pre-built AMP and CloudWatch data source plugins.
- No container to manage or scale.

### Architecture constraints satisfied

- **Private-by-default**: AMP and AMG are accessed via VPC endpoints (PrivateLink).
  No public endpoints are created.
- **Single region `us-east-1`**: All resources in `us-east-1`.
- **Jenkins pipeline**: AMP/AMG are deployed via Terraform `deploy/ecs-app/modules/observability-amp/`
  and activated by the MIDAS Jenkins pipeline.

---

## Consequences

- **New AWS services**: `aps` (AMP) and `grafana` (AMG) are added to the
  solution. Per architecture rules, an ADR is required before adding new service
  types. This is that ADR.
- **New VPC endpoints required**: `com.amazonaws.us-east-1.aps` (AMP) and
  `com.amazonaws.us-east-1.grafana` (AMG). Add to `deploy/ecs-app/` VPC endpoint
  config.
- **New IAM**: EKS node role (ADOT Collector) needs `aps:RemoteWrite`.
  AMG workspace needs `aps:QueryMetrics` + CloudWatch read.
- **ADOT Collector DaemonSet**: A new Helm release in `deploy/observability/otel-collector/`.
  This is a separate Jenkins step, not part of the app release.
- **No double-counting of costs**: AMP pricing is per metric sample ingested.
  Existing CloudWatch EMF metrics and AMP metrics are counted separately; Phase A
  and Phase B can coexist — Phase A is disabled when AMP is fully validated.

---

## Implementation checklist

- [ ] Terraform module `deploy/ecs-app/modules/observability-amp/` — AMP workspace + VPC endpoint + IAM
- [ ] Register module in `deploy/ecs-app/observability.tf`
- [ ] ADOT Collector Helm: `deploy/observability/otel-collector/values.yaml`
- [ ] Grafana dashboard JSON: `deploy/observability/grafana/dashboards/midas-backend-overview.json`
- [ ] Jenkins pipeline step for ADOT Collector Helm deploy (separate from app pipeline)
- [ ] VPC endpoint for `com.amazonaws.us-east-1.aps`

---

## Related

- `docs/adr/0002-midas-kql-log-search.md` — Phase C OpenSearch
- `deploy/ecs-app/modules/observability-app-logs/` — Phase A CloudWatch log group
- `docs/observability-metric-catalog.md` — metric definitions and PromQL queries

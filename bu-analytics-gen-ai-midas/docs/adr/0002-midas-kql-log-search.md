# ADR 0002 — MIDAS KQL Log Search via Amazon OpenSearch Service (Phase C)

| Field | Value |
|---|---|
| Status | Proposed |
| Date | 2026-05-01 |
| Author | MIDAS Platform Team |
| Affects layers | Data, Platform/Infra, CI/CD |

---

## Context

MIDAS backend emits structured JSON logs to CloudWatch Logs (Phase A).
CloudWatch Logs Insights supports a SQL-like query language useful for basic
filtering, but lacks:

- Full-text search across field values
- Kibana Query Language (KQL) — field:value, range, wildcard, boolean operators
- Saved search, dashboards on log data
- Alerting on log content (e.g. alert if `outcome=server_error` rate > threshold
  over the last 15 minutes)

The team wants a log search experience similar to Elasticsearch/Kibana (KQL)
without leaving the AWS private network.

---

## Decision

Deploy **Amazon OpenSearch Service** (managed Elasticsearch-compatible service)
in the MIDAS VPC. OpenSearch Dashboards provides a KQL-compatible query interface
(DQL — Domain Query Language — is a superset of Kibana KQL).

Fluent Bit is **extended with a dual-write output** — logs continue to flow to
CloudWatch Logs (unchanged) and are additionally forwarded to OpenSearch.

```
EKS Pod stdout
  → Fluent Bit DaemonSet (already deployed)
    → CloudWatch Logs (unchanged — Phase A)
    → OpenSearch Service (new — Phase C)
      → OpenSearch Dashboards (DQL / KQL search UI)
```

### Why Amazon OpenSearch over self-managed Elasticsearch?

| Criterion | Amazon OpenSearch Service | Self-managed Elastic |
|---|---|---|
| Operational burden | Low (managed upgrades, snapshots) | High |
| Private-by-default | Yes — VPC mode, no public endpoint | Requires extra effort |
| KQL compatibility | Yes (DQL = KQL superset) | Yes (native KQL) |
| AWS integration | Native (IAM auth, VPC, KMS) | Complex |
| Procurement risk | Zero (AWS-native) | Needs enterprise approval |

### Architecture constraints satisfied

- **Private-by-default**: OpenSearch domain deployed in VPC mode with
  `enforce_https = true`, no public endpoint.
- **Single region `us-east-1`**.
- **Stateless compute**: logs stored in OpenSearch, not on container disk.
- **Event-driven**: Fluent Bit pushes logs as they arrive; no polling.

---

## Consequences

- **New AWS service**: `es` (Amazon OpenSearch Service) is added to the solution.
  This ADR is the required approval gate.
- **Storage cost**: OpenSearch stores log indices. Use ISM (Index State Management)
  policies to roll over and delete old indices. Default: 7-day hot retention.
- **New Fluent Bit output plugin**: `opensearch` output in Fluent Bit values.
  A new Helm values file `deploy/observability/fluentbit/fluentbit-opensearch-values.yaml`
  is added; the existing Fluent Bit DaemonSet is re-deployed (no new DaemonSet).
- **No breaking change to existing log flow**: CloudWatch Logs output is untouched.
  The OpenSearch output is additive.
- **IAM**: The EKS node role needs `es:ESHttpPost` (bulk index) to the OpenSearch
  domain ARN. Fine-grained access control (FGAC) maps the node IAM role to an
  OpenSearch backend role.

---

## Index Design

| Index | Pattern | Retention |
|---|---|---|
| `midas-backend-YYYY.MM.dd` | Daily rolling | 7 days hot, 30 days warm |

Mapping highlights:

- `@timestamp` — ISO 8601, used for time range filter
- `level` — `INFO`, `WARNING`, `ERROR`
- `event` — event type (e.g. `http_request`, `dataset_uploaded`)
- `request_id` — UUID, correlation
- `trace_id`, `user_id`, `tenant_id` — multi-tenant correlation
- `route` — templated URL path
- `outcome` — `success`, `client_error`, `server_error`
- `message` — free text (full-text indexed)
- `@logGroupName` — CloudWatch log group (dual-write correlation)

---

## Implementation checklist

- [ ] Terraform module `deploy/ecs-app/modules/observability-opensearch/`
- [ ] Register module in `deploy/ecs-app/observability.tf`
- [ ] Fluent Bit values: `deploy/observability/fluentbit/fluentbit-opensearch-values.yaml`
- [ ] VPC security group rule: Fluent Bit → OpenSearch port 443
- [ ] ISM policy for index lifecycle (7-day hot, 30-day warm, delete)
- [ ] Index template with mapping above
- [ ] KQL cookbook: `docs/observability-kql-cookbook.md`
- [ ] Jenkins pipeline step to deploy/update Fluent Bit with OpenSearch output

---

## Related

- `docs/adr/0001-midas-amp-amg-observability.md` — Phase B AMP/AMG
- `deploy/observability/fluentbit/fluentbit-opensearch-values.yaml` — Fluent Bit config
- `docs/observability-kql-cookbook.md` — DQL/KQL query examples

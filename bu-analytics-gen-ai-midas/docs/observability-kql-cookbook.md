# MIDAS Observability KQL Cookbook (Phase C)

> **Log search engine**: Amazon OpenSearch Service with OpenSearch Dashboards.
> The query language is **DQL (Domain Query Language)** — a superset of Kibana
> Query Language (KQL). Lucene syntax is also supported in the search bar.

---

## Index pattern

| Pattern | Rotates | Retention |
|---|---|---|
| `midas-backend-*` | Daily (`midas-backend-YYYY.MM.dd`) | 7 days hot, 30 days warm |

Create this pattern in **OpenSearch Dashboards → Stack Management → Index Patterns**.
Set `@timestamp` as the time field.

---

## 1. Basic DQL / KQL queries

### All log lines
```
*
```

### Filter by log level
```
level: ERROR
level: WARNING
```

### Filter by event type
```
event: http_request
event: dataset_uploaded
```

### Find all 5xx errors
```
outcome: server_error
```

### Find all 4xx errors
```
outcome: client_error
```

### Find a specific route
```
route: "/api/v1/datasets/{dataset_id}/upload"
```

---

## 2. Correlation queries

### Trace one request end-to-end
```
request_id: "3fa85f64-5717-4562-b3fc-2c963f66afa6"
```

### Trace by user
```
user_id: "u-1234abcd"
```

### Trace by tenant
```
tenant_id: "acme"
```

### All errors for a specific user in the last hour
```
user_id: "u-1234abcd" AND outcome: server_error
```

---

## 3. Range and performance queries

### Slow requests (over 2 seconds)
```
event: http_request AND duration_ms > 2000
```

### High status codes
```
event: http_request AND status_code >= 500
```

### Combined slow + error
```
event: http_request AND (duration_ms > 2000 OR outcome: server_error)
```

---

## 4. Full-text search

### Search in the message field
```
message: "connection refused"
```

### Wildcard search
```
message: "timeout*"
```

### Phrase match
```
message: "failed to decode"
```

---

## 5. Aggregation visualisations (Dashboards)

Create these in **OpenSearch Dashboards → Visualize → Aggregation-based**.

| Visualisation | Metric | Aggregation | Description |
|---|---|---|---|
| Error rate over time | Count | Date histogram on `@timestamp`, filter `outcome:server_error` | 5xx rate per minute |
| Top slow routes | Average `duration_ms` | Terms on `route` | Identify slowest API routes |
| Request volume heatmap | Count | Date histogram + Terms on `route` | Activity by route over time |
| User error breakdown | Count | Terms on `user_id`, filter `outcome:server_error` | Users hitting most errors |

---

## 6. Saved searches (starter kit)

| Name | DQL | Purpose |
|---|---|---|
| All 5xx | `outcome: server_error` | Incident triage |
| All 4xx | `outcome: client_error` | Client integration issues |
| Slow requests | `duration_ms > 1000 AND event: http_request` | Performance investigation |
| Auth errors | `event: http_request AND status_code: 401 OR status_code: 403` | Auth/authz issues |

Import these via **OpenSearch Dashboards → Stack Management → Saved Objects**.

---

## 7. ISM (Index State Management) policy

Apply this policy to control retention automatically:

```json
{
  "policy": {
    "description": "MIDAS backend log retention: 7-day hot, 30-day warm, then delete.",
    "states": [
      {
        "name": "hot",
        "actions": [],
        "transitions": [{ "state_name": "warm", "conditions": { "min_index_age": "7d" } }]
      },
      {
        "name": "warm",
        "actions": [{ "warm_migration": {} }],
        "transitions": [{ "state_name": "delete", "conditions": { "min_index_age": "30d" } }]
      },
      {
        "name": "delete",
        "actions": [{ "delete": {} }],
        "transitions": []
      }
    ]
  }
}
```

Apply via **OpenSearch Dashboards → Index Management → Policies** or with the API.

---

## 8. Correlating OpenSearch logs with CloudWatch Metrics

Every MIDAS log line contains a `@logGroupName` field (from
`LOG_CLOUDWATCH_LOG_GROUP`). Use it to jump between:

1. Find a `request_id` in OpenSearch Dashboards.
2. Copy the `@logGroupName` value (e.g. `/midas/dev/backend`).
3. Open CloudWatch Logs Insights, select that log group, and run:

```sql
filter request_id = "<paste-request-id>"
| sort @timestamp asc
```

4. From CloudWatch Metrics, view the `HttpRequestDuration` metric for the same
   time window and `Route` dimension.

---

## Related docs

- `docs/adr/0002-midas-kql-log-search.md` — decision record
- `docs/observability-configuration.md` — env var reference
- `docs/observability-metric-catalog.md` — metric catalog
- `deploy/observability/fluentbit/fluentbit-opensearch-values.yaml` — Fluent Bit config

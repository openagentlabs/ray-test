# CloudWatch mapping: MIDAS Terraform (`deploy/ecs-app`) ↔ metrics & logs

This document ties **infrastructure defined in** `deploy/ecs-app` **to** CloudWatch **metric namespaces**, **dimensions**, and **log groups** so you can build dashboards (CloudWatch or Grafana) and Logs Insights queries.  
Application-level OpenTelemetry / EMF is described in [opentelemetry-observability-plan.md](./opentelemetry-observability-plan.md).

**Conventions**

- **`environment`** — Jenkins `TENANT_ENV` / Terraform `var.environment` (e.g. `dev`, `uat`, `prod`).
- **`{region}`** — `var.aws_region`, **always `us-east-1`** for MIDAS ([solution_const.mdc](../.cursor/rules/solution/solution_const.mdc)).
- **Exact resource suffixes** (ALB ARN suffix, RDS final identifier) come from AWS after apply—use the console, **Resource Groups & Tagging**, or `aws resourcegroupstaggingapi` / `aws rds describe-db-instances` if you need the literal dimension string.

---

## 1. Load balancing (NLB + ALB)

**Terraform:** `module.alb_nlb` → `deploy/ecs-app/modules/alb-nlb/main.tf` (when `var.alb_nlb_enabled = true`).

| Component | Name pattern | CloudWatch metrics namespace | Primary dimensions | Notes |
|-----------|--------------|------------------------------|--------------------|--------|
| Internal **ALB** | `midas-{environment}-alb` | `AWS/ApplicationELB` | `LoadBalancer` = `app/midas-{environment}-alb/<suffix>` | Request count, HTTP 4xx/5xx, target response time, active connections. Use **per-listener** or **per-TG** widgets filtered by **Target Group**. |
| ALB TG — **frontend** | `midas-{environment}-alb-fe-tg` | `AWS/ApplicationELB` | `TargetGroup` = `targetgroup/midas-{environment}-alb-fe-tg/<suffix>` | Pod port **8080**; path prefix `/frontend` on ALB. |
| ALB TG — **backend** | `midas-{environment}-alb-be-tg` | `AWS/ApplicationELB` | `TargetGroup` = `targetgroup/midas-{environment}-alb-be-tg/<suffix>` | Pod port **8000**; path prefix `/backend`. |
| ALB TG — **graph** | `midas-{environment}-alb-gr-tg` | `AWS/ApplicationELB` | `TargetGroup` = `targetgroup/midas-{environment}-alb-gr-tg/<suffix>` | Pod port **8001**; path prefix `/graph`. |
| Internal **NLB** | `midas-{environment}-nlb` | `AWS/NetworkELB` | `LoadBalancer` = `net/midas-{environment}-nlb/<suffix>` | TCP flow for corporate → NLB → ALB; use for edge latency/dropped packets vs ALB HTTP metrics. |
| NLB TG → ALB | `midas-{environment}-nlb-alb-tg` | `AWS/NetworkELB` | `TargetGroup` | TCP target health (ALB as target). |

**Dashboard tips**

- One row per **service slice**: NLB (TCP) → ALB (HTTP) → **TargetGroup** `*-be-tg` vs `*-fe-tg` vs `*-gr-tg`.
- Correlate **ALB `HTTPCode_Target_5XX_Count`** with backend pod logs and **MIDAS** custom metrics (below).

---

## 2. Amazon EKS (cluster + nodes)

**Terraform:** `module.eks` → `deploy/ecs-app/modules/eks/main.tf`.

| Component | Name pattern | CloudWatch metrics namespace | Primary dimensions | Notes |
|-----------|--------------|------------------------------|--------------------|--------|
| **Cluster** | `{eks_cluster_name_prefix}-{environment}` (default prefix `midas-eks` → **`midas-eks-{environment}`**) | `AWS/EKS` (control plane–related where enabled) | `ClusterName` | Cluster-level signals available per AWS/EKS docs. |
| **Managed node group** | `{cluster_name}-ng` e.g. **`midas-eks-{environment}-ng`** | **EC2** + **CW Agent** / **Container Insights** if enabled | `AutoScalingGroupName`, instance id | Node CPU/memory/disk come from standard **EC2** / **CWAgent** paths when agents/addons are present—not all are created by this Terraform module. |
| **Control plane logs** | *(log group, not a metric namespace)* | — | — | Log group **`/aws/eks/midas-eks-{environment}/cluster`** (see §5). Log types: `api`, `audit`, `authenticator`, `controllerManager`, `scheduler` (see `cluster_enabled_log_types` in `modules/eks/variables.tf`). |

**Optional:** **Container Insights for EKS** (not defined in `ecs-app` Terraform today) publishes under **`ContainerInsights`** and **`AWS/EKS`** patterns—enable via cluster addon if you want pod-level CPU/memory without Prometheus.

---

## 3. RDS (PostgreSQL)

**Terraform:** `module.rds` → `deploy/ecs-app/modules/rds/main.tf`.

| Component | Name pattern | CloudWatch metrics namespace | Primary dimensions | Notes |
|-----------|--------------|------------------------------|--------------------|--------|
| **DB instance** | Identifier prefix **`midas-{environment}-{region}-pg-`** + unique suffix | `AWS/RDS` | `DBInstanceIdentifier` | **CPU**, **FreeStorageSpace**, **DatabaseConnections**, **ReadLatency** / **WriteLatency**, **ReplicaLag** (if replica added later). |
| **Enhanced Monitoring** | — | — | — | **`monitoring_interval = 0`** in module → **OS-level process list metrics disabled**. Turning on Enhanced Monitoring adds metrics under **`AWS/RDS`** with granularity rules per AWS docs. |
| **Performance Insights** | — | — | — | **`performance_insights_enabled = false`** → no PI counter metrics/dashboards until enabled. |

---

## 4. ElastiCache (Redis)

**Terraform:** `module.elasticache` → `deploy/ecs-app/modules/elasticache/main.tf`.

| Component | Name pattern | CloudWatch metrics namespace | Primary dimensions | Notes |
|-----------|--------------|------------------------------|--------------------|--------|
| **Replication group** | **`midas-{environment}-redis`** (`replication_group_id`) | `AWS/ElastiCache` | `ReplicationGroupId`, `CacheClusterId`, `CacheNodeId` | **CPUUtilization**, **EngineCPUUtilization**, **CurrConnections**, **Evictions**, **ReplicationLag** (multi-AZ). |

---

## 5. CloudWatch **Logs** (infrastructure)

| Source | Log group pattern | Populated by |
|--------|-------------------|--------------|
| EKS control plane | **`/aws/eks/midas-eks-{environment}/cluster`** | `aws_eks_cluster.enabled_cluster_log_types` → Terraform `aws_cloudwatch_log_group.cluster` in `modules/eks/main.tf` |
| Workload / application | **Cluster-dependent** (Fluent Bit / CloudWatch DaemonSet / Pod log routing) | Container stdout → usually **`/aws/containerinsights/...`** or **custom application group**—confirm in CloudWatch → Log groups for the account/region after deploy. |
| RDS PostgreSQL logs | Not enabled in current `modules/rds/main.tf` | To add: `enabled_cloudwatch_logs_exports` on `aws_db_instance` (requires ADR if policy mandates). |
| ALB access logs | Optional S3; not default in `alb-nlb` module | Enable if you need ALB access log **files** (metrics remain in `AWS/ApplicationELB`). |

---

## 6. Application metrics & logs (MIDAS services)

Aligned with [opentelemetry-observability-plan.md](./opentelemetry-observability-plan.md).

| Signal | Where it lands | Namespace / query surface |
|--------|----------------|---------------------------|
| **Structured JSON logs** (FastAPI, `LOG_FORMAT=json`) | Stdout → cluster log pipeline → CloudWatch Logs | **Logs Insights** on the **application log group(s)**; optional field **`@logGroupName`** when `LOG_CLOUDWATCH_LOG_GROUP` is set. |
| **Custom metrics (EMF)** | Stdout EMF lines → agent → CloudWatch Metrics | Custom namespace (planned default **`MIDAS`**); e.g. **`midas.http.request.duration`** with dimensions `method`, `route`, `outcome`. |
| **HTTP request events** | Same JSON pipeline | Filter on **`event` = `http_request`**, **`request_id`**, **`trace_id`** per `logging_config.py`. |

---

## 7. Example dashboard layout (single CloudWatch dashboard)

| Row | Widgets |
|-----|---------|
| **Ingress** | NLB: `ProcessedBytes`, `TCP_ELB_Reset_Count`; ALB: `RequestCount`, `HTTPCode_Target_5XX_Count`, `TargetResponseTime` (split by TG name containing `-be-tg` / `-fe-tg` / `-gr-tg`). |
| **Data plane** | RDS: `CPUUtilization`, `DatabaseConnections`, `FreeStorageSpace`; Redis: `CPUUtilization`, `CurrConnections`, `Evictions`. |
| **App (after OTel)** | Custom namespace **MIDAS**: request duration histogram / stats; alarm on error rate by `outcome`. |
| **EKS** | Control-plane log tail or metric filters; optional Container Insights if enabled. |

---

## 8. Quick dimension lookup (CLI examples)

Replace placeholders with your environment and discover suffixes from AWS:

```bash
# ALB full name for metrics (example)
aws elbv2 describe-load-balancers --region us-east-1 \
  --names "midas-dev-alb" \
  --query 'LoadBalancers[0].LoadBalancerArn'

# RDS instance identifier
aws rds describe-db-instances --region us-east-1 \
  --query "DBInstances[?contains(DBInstanceIdentifier,'midas-dev')].DBInstanceIdentifier"
```

Use the returned **`LoadBalancer`** dimension string (including `app/...` or `net/...`) in dashboard metric widgets.

---

## Related docs

- [opentelemetry-observability-plan.md](./opentelemetry-observability-plan.md) — OTel + EMF + Helm/env wiring.
- `deploy/ecs-app/modules/alb-nlb/main.tf` — ALB/NLB/TG naming.
- `deploy/ecs-app/modules/eks/main.tf` — cluster name and control-plane log group.
- `deploy/ecs-app/modules/rds/main.tf` — RDS identifier prefix and monitoring flags.
- `deploy/ecs-app/modules/elasticache/main.tf` — `replication_group_id` **midas-{env}-redis**.

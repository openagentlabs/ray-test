# ADR 0003 — MIDAS Cross-Pod Per-Dataset Job Locks via ElastiCache Redis (Phase 2)

| Field | Value |
|---|---|
| Status | Proposed |
| Date | 2026-05-13 |
| Author | MIDAS Platform Team |
| Affects layers | Orchestration, Data, Platform/Infra |

---

## Context

`backend/app/services/job_locks.py` (Phase 1) serialises CPU-heavy work on the
same `dataset_id` to prevent the OOM-cascade pattern seen on ~4M-row workloads:
two concurrent jobs (e.g. VIF/correlation finishing while a manual
`train_multiple_models` starts) each hold multi-GB DataFrame copies, breach the
`memory: 53Gi` pod ceiling, and trip the kernel OOM killer. All in-process job
threads die together and the user sees the canonical
`Job was interrupted by server restart. Please retry.` failure.

Phase 1 uses a two-layer pod-local lock:

1. `threading.Lock` per `dataset_id` — collapses parallel threads within one
   Python process to a single waiter.
2. POSIX `fcntl.flock` advisory file lock on top — extends mutual exclusion
   across all gunicorn worker processes in **one pod**.

The module docstring (`job_locks.py` lines 19–25) acknowledges the gap:

> "Cross-pod coordination is intentionally OUT of scope here — that's Phase 2
> (Redis-backed lock via ElastiCache + Celery broker). The ALB's sticky-session
> cookie already pins a given user to one pod for the session, so for the
> immediate user-visible failure pattern a pod-local lock is sufficient."

Three facts make the Phase 1 assumption insufficient for the next release:

1. **Sticky sessions are not actually enabled today.** The backend Service
   annotation `alb.ingress.kubernetes.io/target-group-attributes` in
   `deploy/ecs-app/helm/midas-api-backend-svc/templates/service.yaml` is only
   read by the AWS Load Balancer Controller for Services attached to an
   `Ingress`. MIDAS backends are wired via `TargetGroupBinding` CRDs in
   `deploy/ecs-app/eks-tgb.tf`, and the `aws_lb_target_group "backend"` in
   `deploy/ecs-app/modules/alb-nlb/main.tf` has no `stickiness` block. ALB
   stickiness is therefore unset at the target-group level — a sibling change
   (see "Related" below) enables it. But even with stickiness on, sticky pins
   a browser to a **pod IP**, not to a `dataset_id`.
2. **Two different users on the same dataset still race.** Stickiness pins
   **users**, not datasets. User A on pod 1 and user B on pod 2 can both kick
   off heavy jobs against the same `dataset_id` concurrently. The fcntl lock
   does not span pods, so both pods run heavy jobs against the same dataset
   and exhibit the OOM cascade across pods rather than within one.
3. **MIDAS needs to scale beyond a single backend replica.** The Helm
   `values.schema.json` currently caps `replicaCount` at 1 explicitly to avoid
   this cross-pod race. To safely raise that cap, cross-pod coordination must
   exist first.

---

## Decision

Add a **third coordination layer in front of the existing thread + fcntl
flow**: an exclusive lock keyed on `dataset_id`, held in the existing MIDAS
ElastiCache Redis cluster, using the canonical `SET key value NX PX <ttl>`
pattern with a fencing token, a background heartbeat to extend TTL on
long-running jobs, and a compare-and-delete Lua release.

Order of acquisition (top wins):

```
Redis SETNX  (cross-pod authoritative)
  └─ on Redis unavailable, fall back to ─→ fcntl flock  (per-pod)
                                              └─ thread.Lock  (per-process)
```

The full Phase 1 thread + fcntl path is **retained** as a fallback so:

- Local dev (no ElastiCache) keeps working.
- A Redis outage degrades to current per-pod behaviour rather than failing
  open or failing closed entirely.
- The blast radius of the new code is small — Redis is added in front of, not
  in place of, the proven Phase 1 path.

### Lock data shape

| Aspect | Choice |
|---|---|
| Key | `midas:dslock:<dataset_id>` |
| Value | 32-hex-char fencing token (per acquire, secrets.token_hex(16)) |
| Acquire | `SET key token NX PX <ttl_ms>` |
| Release | Lua: `if get == token then del key` (compare-and-delete) |
| Default TTL | 30 minutes (configurable via `DATASET_LOCK_TTL_MS`) |
| Heartbeat | Every 30 s, `PEXPIRE key <ttl_ms>` while job is running |
| Wait poll | 2 s, with timeout from caller |
| Crash safety | Pod OOM-killed → lock auto-expires after TTL; no manual recovery |

### Reuse of existing ElastiCache

MIDAS already runs an ElastiCache Redis replication group provisioned by
`deploy/ecs-app/elasticache.tf` (default `var.elasticache_redis_enabled = true`).
The cluster is private (VPC), encrypted at rest and in transit, and the AUTH
token + connection URL live in Secrets Manager (`elasticache_redis_auth_secret_arn`).
It is already consumed by:

- Session store (`SESSION_REDIS_URL` / `SESSION_REDIS_SECRET_ID`)
- Rate limiter (`RATE_LIMIT_REDIS_URL`)
- RFE worker event bus (`backend/app/services/model_training_rfe/event_bus/redis_bus.py`)

This ADR adds a **new use of the existing data store**, not a new data store.
Per `architecture.mdc`, adding a new data store requires user approval. Adding
a new use of an existing store does not, but is documented in an ADR for
traceability.

### Architecture constraints satisfied

- **Private-by-default**: traffic to ElastiCache stays inside
  `vpc-0c4d673f3e95a93eb`; TLS via `rediss://`.
- **Single region `us-east-1`**: same cluster as RDS, EKS, S3.
- **Stateless compute**: lock state lives in Redis; pods remain stateless and
  may be replaced without manual recovery (TTL handles orphaned locks).
- **Event-driven by default**: lock waiters poll Redis rather than blocking
  on an in-process queue.
- **No new AWS service**: reuses existing `elasticache` module.

---

## Consequences

- **New library dependency**: `redis` (`redis-py`) is already pinned for the
  RFE worker; no new requirements line. If a dedicated client is preferred
  for the lock (e.g. `aioredis`), evaluate before adding.
- **New env var**: `DATASET_LOCK_TTL_MS` (optional; defaults to 30 minutes).
  Sourced from Helm `values.yaml`; not stored in Secrets Manager because the
  TTL is not sensitive.
- **New Helm value**: `redisLock.ttlMs` mirroring `DATASET_LOCK_TTL_MS`.
- **Helm `replicaCount` cap raised**: `values.schema.json` maximum bumped from
  1 to 5 (initial target). Sibling change; gated on this ADR being implemented
  first.
- **Observability**:
  - Structured log event `dataset_job_lock_acquired` with `dataset_id`,
    `job_label`, `wait_seconds`, `backend` (`redis` | `fcntl` | `thread`).
  - Structured log event `dataset_job_lock_released` mirroring the above.
  - Structured log event `dataset_job_lock_timeout` with the same fields plus
    `timeout_seconds`.
  - CloudWatch metric (EMF) `midas.job_lock.wait_seconds` (histogram).
- **Failure mode 1 — Redis outage**: the Redis acquire raises a
  `redis.exceptions.ConnectionError`; the code logs a warning and falls back
  to the fcntl + thread path. Result: temporarily degrades to per-pod
  behaviour, no user-visible failure. Backends scale to 1 should be the
  operator response; alert on `dataset_job_lock_redis_unavailable` rate > 0.
- **Failure mode 2 — pod OOM-killed while holding the lock**: TTL expires
  after `DATASET_LOCK_TTL_MS` (default 30 min). No manual `redis-cli DEL`
  required. Heartbeat thread dies with the pod, so TTL countdown is honest.
- **Failure mode 3 — clock skew**: `SET NX PX` is server-evaluated; client
  clock is irrelevant. Heartbeat uses `PEXPIRE`, also server-side. Clock skew
  has no impact.
- **Failure mode 4 — split-brain (Redis failover)**: ElastiCache replication
  group with `multi_az_enabled` and `automatic_failover_enabled` (already set
  in `aws_elasticache_replication_group "redis"` when `num_cache_clusters > 1`).
  A failover may briefly expose two pods both holding the lock; the fencing
  token + compare-and-delete release prevents accidental release of the
  other's lock, but does **not** prevent concurrent work during the brief
  window. Acceptable for current scale (operations are minutes long, failover
  is seconds); revisit with Redlock if needed.
- **No effect on Phase 1 callers**: the public API
  `dataset_job_lock(dataset_id, job_label, ...)` is unchanged. Existing
  callers in `backend/app/api/routes.py` and the training runners need no
  edits.

---

## Implementation checklist

- [ ] Extend `backend/app/services/job_locks.py` with:
  - `_redis_client_for_locks()` — resolves from `SESSION_REDIS_URL` /
    Secrets Manager / `REDIS_URL`, returns `None` on any failure.
  - `_acquire_redis_lock(dataset_id, job_label, wait, timeout_seconds)` —
    `SET NX PX` + 2s poll loop + heartbeat thread.
  - `_release_redis_lock(dataset_id, token)` — Lua compare-and-delete.
  - Public `dataset_job_lock(...)` updated to try Redis first, fall back on
    `ConnectionError` / unavailable client.
- [ ] Add env var `DATASET_LOCK_TTL_MS` to
  `deploy/ecs-app/helm/midas-api-backend-svc/templates/deployment.yaml`,
  sourced from a new `redisLock.ttlMs` value in `values.yaml`.
- [ ] Verify `envFrom: midas-app-secret` in the same deployment template
  surfaces `SESSION_REDIS_URL` (already populated by `populate-secrets.sh`).
- [ ] Tests:
  - Unit: `tests/services/test_job_locks_redis.py` — acquire / release,
    contention with two simulated pods (via two `redis-py` clients), TTL
    expiry, compare-and-delete safety.
  - Integration: `tests/integration/test_dataset_job_lock_redis.py` runs
    against a real Redis container in CI.
  - Fallback: simulate Redis down → verify fcntl path activates and the
    `dataset_job_lock_redis_unavailable` log event fires.
- [ ] Observability:
  - `app/core/logging_config.py` event registry: add `dataset_job_lock_*`
    events to the known-event allowlist.
  - EMF metric `midas.job_lock.wait_seconds` emitted from acquire path.
- [ ] Sibling change (separate PR, gated on this one): raise
  `replicaCount.maximum` in
  `deploy/ecs-app/helm/midas-api-backend-svc/values.schema.json` from 1 to 5,
  and adjust `strategy.maxSurge` / `maxUnavailable` in the deployment template
  so rolling updates work with multiple replicas.

---

## Alternatives considered

- **Redlock (multi-Redis quorum)**: overkill for the current single-replication-
  group cluster; introduces multi-node coordination complexity for a workload
  whose individual operations are minutes long and where a brief failover
  overlap is acceptable. Revisit if scale grows.
- **PostgreSQL advisory locks (`pg_advisory_lock`)**: works, but adds DB load
  on a path that is already under pressure during 4M-row workloads, and
  requires holding a DB connection for the duration of the job (10–30 min).
  Connection pressure outweighs the simplicity gain.
- **Kubernetes Lease / coordination.k8s.io**: usable for leader-style locks
  but ergonomics for per-`dataset_id` keys are poor (Lease per dataset is not
  idiomatic). Also requires the backend pod's ServiceAccount to have RBAC on
  leases.
- **In-process queue with a single "scheduler" pod**: changes the deployment
  topology, introduces a single-point-of-failure, and requires a leader
  election mechanism — which itself would use Redis. Net negative.

---

## Related

- `backend/app/services/job_locks.py` — Phase 1 thread + fcntl implementation
  that this ADR augments.
- `deploy/ecs-app/elasticache.tf` and `deploy/ecs-app/modules/elasticache/` —
  existing ElastiCache module reused by this ADR.
- `backend/app/core/config.py` — `SESSION_REDIS_URL`, `REDIS_URL`,
  `SESSION_REDIS_SECRET_ID` already plumbed.
- `backend/app/services/model_training_rfe/event_bus/redis_bus.py` — existing
  redis-py usage pattern in the codebase; the lock implementation should
  mirror its connection / TLS / auth handling.
- `backend/docs/midas-4m-row-performance-analysis 1.md` — performance
  analysis that identifies the lock-hold time as part of the 30–40 min →
  3–5 min target band.
- `.cursor/plans/4m_row_performance_fixes_4cc2ea83.plan.md` — the parent plan
  that schedules this ADR alongside the perf fixes and the stickiness /
  replica-cap changes.
- `docs/adr/0001-midas-amp-amg-observability.md` — ADR format precedent.

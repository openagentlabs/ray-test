# Worker shared-state audit

**Scope:** `backend/app` — multi-worker / multi-pod correctness when any worker must be able to serve any request (for example three gunicorn or uvicorn workers behind a load balancer).

**Related artifact:** Interactive table and phased plan live in the Cursor canvas `canvases/worker-shared-state-audit.canvas.tsx` (IDE-managed path under the Cursor project).

**Last updated:** May 2026

---

## Summary

| Traffic | Count | Meaning |
|--------|------:|---------|
| Red (Critical) | 5 | 404s, split-brain, or silent loss of progress across workers |
| Orange (High) | 6 | Auth / rate-limit bypass, divergent job state, or duplicate subprocesses |
| Yellow (Medium) | 7 | Duplicated work, inconsistent caches, or 404 only in specific modes |
| Green (Low) | 5 | Acceptable per-process caches or documented local-only behaviour |

**Recommendation:** Address all **Critical** and **High** items before treating horizontal scale as safe.

---

## Traffic light legend

| Light | Severity | Typical impact |
|-------|----------|----------------|
| Red | Critical | Wrong pod → 404, missing events, or duplicate jobs |
| Orange | High | Session / limit semantics wrong; state on local disk only |
| Yellow | Medium | Extra cost or brief inconsistency; some cases fixed by fixing Critical (RFE) |
| Green | Low | Performance or convenience only; no cross-worker correctness requirement |

---

## Findings table

Paths below are relative to `backend/app/` unless noted.

| Light | ID | Area | File | Symbol / state | State type | Problem | Recommended fix |
|-------|----|------|------|------------------|------------|---------|-------------------|
| Red | C1 | DataFrame State | `services/dataframe_state_manager.py` | `DataFrameStateManager` | In-memory singleton | Live pandas DataFrames (transforms, splits, version counters) held per worker. Mutations on one worker are invisible to others; transforms or split config can 404 or go stale. | Persist DataFrames and transform metadata to S3; load on demand per request. |
| Red | C2 | SSE Event Bus | `api/sse.py` | `_QUEUES` / `_LAST_ACTIVITY` | `asyncio.Queue` per `dataset_id` | Subscribers bind to one worker’s event loop; publisher on another worker cannot deliver events. | Redis Pub/Sub (or equivalent); each worker subscribes to the same channel. |
| Red | C3 | RFE Pipeline | `services/model_training_rfe/backends.py` | `_JOB_STATE` / `_EVENT_BUS` / `_JOB_QUEUE` | In-memory + asyncio queue | Default `RFE_SCALING_MODE=local`: job state, bus, and queue are in-process. Status poll or SSE on another pod → 404. | Set `RFE_SCALING_MODE=redis` and `REDIS_URL`; use S3 artifact backend. |
| Red | C4 | Chunked Upload | `api/chunked_upload.py` | `_uploads` `Dict[upload_id]` | Per-process dict | PATCH/finalize must hit the same pod as POST; otherwise upload context missing → 404. | Redis keyed by `upload_id`, or sticky sessions for the upload flow. |
| Red | C5 | Classification & Auto-Training Jobs | `api/routes.py` | `_classification_jobs` / `_active_auto_training_by_dataset` | Module-level dicts | Job status on a different pod than the starter → 404. Two pods can both think no job is running. | Job status in Redis or DB; atomic check-and-set for slot acquisition. |
| Orange | H1 | Background Job Manager | `services/background_jobs.py` | `BackgroundJobManager._jobs` | In-memory dict + local JSON | S3 snapshots are authoritative, but `_jobs` is per-process; `background_jobs_state.json` is container-local. | Drop local JSON; read job status from S3/DB only. |
| Orange | H2 | Legacy Training Jobs State | `api/routes.py` | `training_jobs` / `split_configs` | In-memory dict + local JSON | `training_jobs_state.json` / `split_configs_state.json` on local disk; pods diverge at import. | Migrate to `background_job_manager`; remove local JSON persistence. |
| Orange | H3 | Session Store | `core/session/session_backends.py` | `InMemorySessionStore` | `Dict[session_id, session]` | Sessions on pod A unknown on pod B after re-route. | Never use in-memory sessions outside local dev; assert Redis in non-local profiles; keep `REDIS_URL` set. |
| Orange | H4 | Rate Limit Store | `core/rate_limit_store.py` | `InMemoryRateLimitStore._counts` | Per-process counters | Without Redis, effective limit ≈ limit × number of workers. | Always use Redis-backed store in shared environments; assert at startup. |
| Orange | H5 | GraphRAG Process Manager | `services/graphrag_process_manager.py` | `GraphRAGProcessManager._process` | Subprocess per worker | Each worker may fork GraphRAG locally; traffic to another worker sees no process. | Run GraphRAG as a separate service; workers call over HTTP/gRPC. |
| Orange | H6 | Vector Store (FAISS) | `services/vector_store.py` | `self.index` / `self.documents` | FAISS in-memory + local path | Index updates on one worker not visible on others until reload. | Reload from shared storage on a TTL, or use OpenSearch k-NN (aligned with MIDAS data layer). |
| Yellow | M1 | RFE Job State (in-memory) | `services/model_training_rfe/job_state/in_memory.py` | `InMemoryJobStateStore._rows` | Per-process dict | GET on different pod than POST → 404 when `RFE_SCALING_MODE=local`. | Fix C3 (redis mode). |
| Yellow | M2 | RFE Filesystem Artifacts | `services/model_training_rfe/storage/filesystem_backend.py` | `FilesystemBackend` / `RFE_ARTIFACTS_DIR` | Local pod disk | Artifacts on one pod not visible on another → 404 on download. | Fix C3 + S3 storage backend. |
| Yellow | M3 | Insight Caches | `api/routes.py` | `_bivariate_cache` / `_correlation_cache` / `_corr_matrix_cache` | TTL dict per process | Cold workers repeat work; brief cross-worker inconsistency. | Shared Redis cache or document L1 staleness. |
| Yellow | M4 | LLM / KG Progressive Cache | `services/llm_service.py` | `_kg_progressive_cache` | Module-level dict | Status on another pod empty or 404 vs in-progress. | Redis + TTL for build state. |
| Yellow | M5 | Modelling Artefact Cache | `services/message_state_service.py` | `MessageStateManager._modelling_artifacts_cache` | Per-instance dict | Cache hits differ by pod; DB fallback exists but behaviour diverges. | Remove in-memory layer; read DB/S3 each time if needed. |
| Yellow | M6 | Segmentation Stability Cache | `services/segmentation_stability.py` | `BootstrapStabilityAnalyzer._cache` | In-memory TTL | Heavy work repeated per worker. | Redis keyed by dataset + config hash. |
| Yellow | M7 | GraphRAG / KG Disk Cache | `services/graphrag_service.py` | `self._cache` / `backend/kg_cache` | In-memory + local disk | Pod-local cache; other workers re-fetch. | Shared `MIDAS_KG_CACHE_DIR` (EFS/S3-backed); optional L1 in memory. |
| Green | L1 | Analytics L1 Cache | `services/analytics_cache.py` | `AnalyticsResultCache._cache` | OrderedDict + optional Redis L2 | Per-process L1; duplicate compute, not a correctness bug. | Ensure `REDIS_URL` for L2 where desired. |
| Green | L2 | Dataset Parse Cache | `services/dataset_service.py` | `_SharedDataFrameLoadCache` | LRU+TTL per process | Duplicate parses per worker. | OK as-is; optional shared cache. |
| Green | L3 | JWKS Cache | `services/cognito/jwks.py` | `_JwksCache` | Per-process in-memory | Extra fetches on cold workers. | OK as-is. |
| Green | L4 | File-based Job Locks | `services/job_locks.py` | `_THREAD_LOCKS` / fcntl | Thread + file locks | Same-node directory only; not cross-pod. | Redis distributed lock for cross-pod exclusion. |
| Green | L5 | Sidecar Cache | `services/sidecar_cache.py` | `SidecarCache` | Local `/tmp` + OrderedDict | Documented process-local; other pods re-download. | OK as-is; optional shared dir for bandwidth. |

---

## Phased remediation plan

### Phase 1 — Fix 404s and split-brain (Critical)

- **C1** — DataFrame State  
- **C2** — SSE Event Bus  
- **C3** — RFE Pipeline (redis + S3)  
- **C4** — Chunked Upload  
- **C5** — Classification & Auto-Training Jobs  

### Phase 2 — Auth and rate-limit safety (High)

- **H1** — Background Job Manager  
- **H2** — Legacy Training Jobs State  
- **H3** — Session Store  
- **H4** — Rate Limit Store  
- **H5** — GraphRAG Process Manager  
- **H6** — Vector Store (FAISS)  

### Phase 3 — Reduce duplicated work (Medium)

- **M1**–**M7** — As listed above (M1/M2 largely addressed by C3)

### Phase 4 — Efficiency (Low)

- **L1**–**L5** — As listed above

---

## Method

Static code review of `backend/app` for module-level mutable state, per-process caches, local filesystem persistence of authoritative state, and in-process queues or buses that do not use Redis, S3, RDS, or ElastiCache as the source of truth across replicas.

---

## Architecture note

MIDAS is private-by-default in `us-east-1` with managed state (RDS, ElastiCache, S3, OpenSearch). Remediation should align with that model: shared stores and PrivateLink-accessible services, not new public endpoints. If a new shared service type is required, capture the decision in `docs/adr/` per project rules.

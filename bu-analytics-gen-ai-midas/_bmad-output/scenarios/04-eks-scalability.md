# Scenario 4 — EKS scalability (large CSV, multi-user)

## Goals

- **Near-term:** ~5 concurrent heavy users, **~5 GB CSV** per upload path
- **Target:** ~20 concurrent users, **~20 GB CSV** per upload path
- **Platform:** AWS-first, EKS-deployable; no structural rewrite between 5 and 20 users/pods

## Skill chain

Same shape as scenario 2 (architecture-first), with infra and ops gates:

| Step | Skill | Primary output |
|---|---|---|
| 1 | `bmad-technical-research` | `planning-artifacts/<slug>/research-eks-csv.md` |
| 2 | `bmad-create-architecture` | `planning-artifacts/<slug>/architecture-eks-scale.md` (+ memory budget table) |
| 2★ | `bmad-party-mode` | `planning-artifacts/epics/<slug>/party-reviews/architecture-roundtable.md` — **Winston (architect)** reviews Helm/EKS/memory |
| 3 | `bmad-spec` | `specs/spec-<slug>/SPEC.md` + companions |
| 4 | `bmad-create-story` | `implementation-artifacts/<slug>/story-ST-*.md` |
| 5 | `bmad-dev-story` | Code + perf tests + ops checklist |
| 6 | `bmad-code-review` | Scale + memory review |

Use the same **feature slug** from intake through all paths (see `intake/README.md`). Example slug: `eks-large-csv-scale`.

Copy-paste prompts: [_bmad-output/How to use BMAD for each scenario.md](../How%20to%20use%20BMAD%20for%20each%20scenario.md#scenario-4--eks-scalability).

## Architectural anchors (repo-grounded)

| Concern | Existing pattern |
|---|---|
| Large uploads | Chunked upload API (`backend/app/api/chunked_upload.py`, tests in `test_chunked_upload.py`) |
| Blob storage | S3 presigned / upload prefix (`S3_UPLOAD_KEY_PREFIX` in config) |
| Cross-pod job status | S3 snapshots in `background_jobs.py` (`midas_bg_jobs/`) |
| Session / rate limit | ElastiCache Redis |
| Transactional SoR | RDS PostgreSQL (`exldecision-ai-modellab`) |
| Compute | EKS + Helm `midas-api-backend-svc` (`replicaCount`, `webConcurrency`, high memory requests) |

## Hard constraints (wire into SPEC and architecture)

From `_bmad-output/project-context.md` (Large data, memory, and EKS scale):

| Constraint | Rule |
|---|---|
| **S3 for blobs** | Files above the chunked-upload threshold land in **S3** (multipart/presigned). Postgres holds metadata only. |
| **Redis-backed coordination** | Job queue status, locks, session, and rate limits use **ElastiCache Redis** — not in-pod queues. |
| **Stateless pods** | No durable in-pod state for user jobs or datasets; cross-replica via **S3** + **Redis** only. |
| **No whole-file CSV in RAM** | Never load 5–20 GB CSV into process memory; streaming/chunked reads only. |
| **Bounded caches** | Max entries + TTL; document **pod × worker × cache entry** RAM in architecture. |
| **Helm awareness** | Changes to `replicaCount`, `webConcurrency`, or memory requests require explicit memory math. |

## Mandatory party-mode (architecture gate)

Before `bmad-spec` or large `bmad-dev-story` work, run **`bmad-party-mode`** with:

- **Winston (architect)** — Helm/EKS, replica/worker memory, HPA, no sticky sessions
- **John or Mary (PM)** — SLOs and intake targets (5 vs 20 users, 5 vs 20 GB)
- **Amelia (dev)** — implementation risks on `chunked_upload.py`, `background_jobs.py`

**Prompt hint:**

```
Use bmad-party-mode. Scenario 4 EKS scale, slug <slug>.
Gate: architecture review before spec/dev.
Agents: Winston (Helm/EKS/memory), John or Mary (SLOs), Amelia (dev).
Read: planning-artifacts/<slug>/architecture-eks-scale.md, deploy/ecs-app/helm/midas-api-backend-svc/, project-context.md large-data section.
Save: planning-artifacts/epics/<slug>/party-reviews/architecture-roundtable.md
Proceed only if Winston confirms memory table and no whole-file RAM paths.
```

Configured in `_bmad/custom/bmad-party-mode.toml` (Winston required for EKS/Helm on feature reviews).

## Preconditions

Intake in `_bmad-output/intake/04-eks-scalability/`:

- Concurrent user count (5 vs 20), CSV size distribution
- SLOs (upload time, processing time, error budget)
- Current pain (OOM, timeouts, stuck jobs)
- **Slug** chosen for this initiative (e.g. `eks-large-csv-scale`)

## Workflow steps

### 1. Research (`bmad-technical-research`)

**Prompt:**

```
Use bmad-technical-research. Topic: MIDAS EKS scale for 5–20 users and 5–20 GB CSV uploads.
Compare: chunked S3 ingest, streaming pandas/polars, worker pool sizing, Redis locks, HPA metrics.
Cite existing code: chunked_upload, background_jobs S3 snapshots, Helm values.yaml replicaCount/webConcurrency.
```

### 2. Architecture (`bmad-create-architecture`)

Must include explicit **memory budget table**:

| Dimension | Question to answer |
|---|---|
| Per chunk size | Max bytes in flight per request |
| Per worker | Gunicorn workers × chunk buffers |
| Per pod | Workers + any singleton cache |
| Cluster | Replicas × pod memory vs node allocatable |

**Prompt:**

```
Use bmad-create-architecture for EKS large-CSV scale. Slug: <slug>. Output to planning-artifacts/<slug>/.
Include memory table for 5 and 20 users. Reference ADR 0003 Redis cross-pod locks if relevant.
State S3 blob threshold, Redis job coordination, and stateless pod rules from project-context.md.
```

### 3. Party-mode architecture review (`bmad-party-mode`)

See [Mandatory party-mode](#mandatory-party-mode-architecture-gate) above.

### 4. Spec (`bmad-spec`)

Slug: same as intake (e.g. `eks-large-csv-scale`).

Constraints must state: S3 blobs above threshold, Postgres metadata, Redis-backed job queue, stateless pods, no full-file RAM, bounded caches with TTL.

### 5. Implement (`bmad-dev-story`)

Stories should touch tests first (perf ceiling, chunked paths, concurrent status polling).

### 6. Verify (required — not optional)

**Automated**

- Extend `backend/tests/test_chunked_upload.py` or perf tests (`test_partition_preview_perf.py` pattern)
- Load tests documented even if run manually in dev

**Operational checklist (attach to PR)**

- [ ] `helm template` reviewed for replicaCount / webConcurrency / resources
- [ ] Concurrent upload test (N users) — no OOMKill
- [ ] Job status poll works from arbitrary pod (S3 snapshot)
- [ ] Redis lock behavior under multi-replica (if applicable)
- [ ] CloudWatch log queries for `event` keys on new paths

### 7. Review (`bmad-code-review`)

Require reviewer to confirm memory table and test evidence.

## Definition of done

Scenario 4 work is **not complete** until all of the following:

1. **Load test** — N concurrent users (document N: 5 near-term or 20 target) each uploading/processing up to X MB/GB (document X per intake SLO) completes without error.
2. **No OOM** — No pod restart from OOMKill during the load test; memory table in architecture matches observed usage.
3. **Helm** — `deploy/ecs-app/helm/midas-api-backend-svc/` values updated (replicaCount, webConcurrency, resources) and reviewed via `helm template`.
4. **Jenkins** — Pipeline green for deploy to dev (or documented manual deploy with build number).
5. **Tests** — pytest evidence for chunked/streaming paths (no full-file read); output pasted in PR or story.
6. **Review** — `bmad-code-review` passed; Winston roundtable synthesis attached if architecture changed.

Optional: file a **Jira ticket** for the initiative before phase 1 if the team needs prioritisation and sprint tracking (recommended when OOM/large-CSV is production-active).

## Escalation

| Situation | Action |
|---|---|
| Needs new AWS service | ADR + user approval per architecture.mdc |
| Sticky sessions proposed | Challenge — prefer shared Redis/S3; document trade-off |
| Frontend loads full CSV | Route to scenario 1 UX + streaming APIs |

## Completion checklist

- [ ] Architecture memory math for 5 and 20 users
- [ ] SPEC constraints cite S3, Redis queue, stateless pods, no whole-file RAM
- [ ] Party-mode architecture-roundtable.md (Winston) on file
- [ ] No full-file load in code paths
- [ ] Definition of done (load test, no OOM, Helm, Jenkins, tests, review)
- [ ] Tests + ops checklist attached

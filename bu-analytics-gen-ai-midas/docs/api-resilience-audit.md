# MIDAS API Resilience Audit

*Frontend client analysis — `fastApiService.ts` · `apiInterceptor.ts` · `apiServices.ts` · `creditRiskApi.ts`*

*Companion: Cursor canvas `api-resilience-audit.canvas.tsx` (same structure and tables; this file is the markdown export for `docs/`).*

---

## Summary

| Metric | Value |
|--------|------:|
| Endpoints audited | 60 |
| Gold standards checked | 15 |
| Gold standards failing | 11 |
| Gold standards partial | 4 |

### Key finding

Three separate API clients (`fastApiService`, `apiInterceptor`, `creditRiskApi`) are in use for the MIDAS backend. Most calls use plain `fetch()` with no timeout, no retry, and no backoff. Polling loops have no N-failure abort and no counter reset on success.

---

## Legend (traffic light)

| Token | Meaning |
|-------|---------|
| **Pass** | Meets or intentionally satisfies the criterion |
| **Partial** | Some coverage or acceptable trade-off |
| **Fail** | Missing or does not meet the criterion |

---

## Client architecture

| Client | Used by | 401 refresh | Timeout support | Retry support | Base URL source |
|--------|---------|-------------|-----------------|---------------|-----------------|
| `apiInterceptor` | Project routes, dataset/scope, auth routes | Yes — one refresh+retry | None (no `AbortController`) | None | `VITE_BASE_URL` → `/api/v1` |
| `FastAPIService` | Data / ML / training routes (~90% of calls) | `fetchWithAutoRefresh` (most) **or** plain `fetch` (many) | Only `analyzeDataset` & `uploadDataset` | Only `analyzeDataset`, `validateUniqueIds`, chunked chunks | `VITE_BASE_URL` → `/api/v1` |
| `creditRiskApi` | Credit-risk model builder routes | Headers added, no refresh logic | None | None | Hardcoded `localhost:3001` (dev) / `/api` (prod) |
| `apiServices` (FRED / FMP / Gemini) | External data & AI APIs | N/A (external) | None | None | Hardcoded prod URLs |

---

## Short-lived requests

*Expected to return quickly — simple reads, auth, config.*

**Gold standard:** timeout (≤10s), retry-on-error (min 2×), retry-on-timeout, exponential backoff with jitter, 401 auto-refresh.

| Endpoint | Client | Timeout | Retry error | Retry timeout | Backoff | Notes |
|----------|--------|---------|-------------|---------------|---------|-------|
| `GET /health` | fastApiService | Fail | Fail | Fail | Fail | Plain fetch, no timeout, no retry |
| `GET /datasets` | fastApiService | Fail | Fail | Fail | Fail | Plain fetch, no timeout, no retry |
| `GET /datasets/{id}/stats` | fastApiService | Fail | Fail | Fail | Fail | Plain fetch, no timeout, no retry |
| `GET /datasets/{id}/raw-data` | fastApiService | Fail | Fail | Fail | Fail | Plain fetch, no timeout, no retry |
| `GET /datasets/{id}/column-info` | fastApiService | Fail | Fail | Fail | Fail | Plain fetch, no timeout, no retry |
| `GET /datasets/{id}/dqs` | fastApiService | Fail | Fail | Fail | Fail | Plain fetch, no timeout, no retry |
| `GET /datasets/{id}/dqs-by-scope` | fastApiService | Fail | Fail | Fail | Fail | Plain fetch, no timeout, no retry |
| `GET /datasets/{id}/column-info-by-scope` | fastApiService | Fail | Fail | Fail | Fail | Plain fetch, no timeout, no retry |
| `GET /datasets/{id}/export` | fastApiService | Fail | Fail | Fail | Fail | Plain fetch, no timeout, no retry |
| `DELETE /datasets/{id}` | fastApiService | Fail | Fail | Fail | Fail | Plain fetch, no retry |
| `GET /chat/{id}/history` | fastApiService | Fail | Fail | Fail | Fail | Plain fetch, no timeout, no retry |
| `DELETE /chat/{id}/reset` | fastApiService | Fail | Fail | Fail | Fail | Plain fetch, no retry |
| `GET /llm-config` | fastApiService | Fail | Fail | Fail | Fail | `fetchWithAutoRefresh`, no timeout, no retry |
| `GET /llm-models` | fastApiService | Fail | Fail | Fail | Fail | `fetchWithAutoRefresh`, no timeout, no retry |
| `GET /keepalive` | fastApiService | Fail | Pass | Pass | Pass | Silent ignore is correct for keepalive |
| `POST /dataset/scope` | apiInterceptor | Fail | Pass | Partial | Fail | `apiInterceptor`; 401-refresh OK; no timeout/backoff |
| `GET /auth/me` | apiInterceptor | Fail | Pass | Partial | Fail | `apiInterceptor`; 401-refresh OK; no explicit timeout |
| `GET /projects` | apiInterceptor | Fail | Pass | Partial | Fail | `apiInterceptor`; 401-refresh OK; no explicit timeout |
| `GET /model-evaluation/list/all` | fastApiService | Fail | Fail | Fail | Fail | Plain fetch, no retry |
| `GET /model-evaluation/{id}` | fastApiService | Fail | Fail | Fail | Fail | Plain fetch, no timeout, no retry |
| `GET /auth/cognito/login-url` | fastApiService | Fail | Fail | Fail | Fail | Plain fetch, no retry |
| `POST /auth/cognito/exchange` | fastApiService | Fail | Fail | Fail | Fail | Critical token mint — no retry/timeout |
| `POST /auth/cognito/refresh` | fastApiService | Fail | Partial | Fail | Fail | 401 handled via `httpUnauthorized`, no timeout |

---

## Long-lived requests

*Heavy computation / large DataFrame processing — can take minutes on large files.*

**Gold standard:** scaled timeout, retry-on-error (≥2×), retry-on-timeout, backoff, keepalive during call, cancellation support.

| Endpoint | Client | Scaled timeout | Retry error | Retry timeout | Backoff | Keepalive | Notes |
|----------|--------|----------------|-------------|---------------|---------|-----------|-------|
| `POST /upload` | fastApiService | Pass | Fail | Fail | Fail | Pass | `computeIngestTimeout` scales with file size. No retry on error/timeout. Keepalive: yes |
| `POST /analyze-dataset` | fastApiService | Pass | Pass | Pass | Partial | Pass | Retry ×3, linear 3s/6s delay (not exponential). Timeout scales. Keepalive: yes |
| `POST /partition-preview` | fastApiService | Fail | Fail | Fail | Fail | Fail | Plain fetch, no timeout, no retry, no keepalive |
| `POST /partition-preview-by-id` | fastApiService | Fail | Fail | Fail | Fail | Fail | Plain fetch, no timeout, no retry, no keepalive |
| `POST /exclusion-preview` | fastApiService | Fail | Fail | Fail | Fail | Fail | Plain fetch, no timeout, no retry, no keepalive |
| `POST /exclusion-preview-by-id` | fastApiService | Fail | Fail | Fail | Fail | Fail | Plain fetch, no timeout, no retry, no keepalive |
| `POST /variable-review/preview` | fastApiService | Fail | Fail | Fail | Fail | Fail | `fetchWithAutoRefresh`, no timeout/retry/keepalive |
| `POST /variable-review/run` | fastApiService | Fail | Fail | Fail | Fail | Fail | `fetchWithAutoRefresh`, no timeout/retry/keepalive |
| `POST /chat` | fastApiService | Fail | Fail | Fail | Fail | Fail | `fetchWithAutoRefresh`, no timeout, no retry |
| `POST /insights/correlation-matrix` | fastApiService | Fail | Fail | Fail | Fail | Fail | `postInsightFormResolve202` — no timeout/retry for the 202 GET polls |
| `POST /insights/iv-analysis` | fastApiService | Fail | Fail | Fail | Fail | Fail | Same as correlation-matrix |
| `POST /insights/vif-analysis-dedicated` | fastApiService | Fail | Fail | Fail | Fail | Fail | Same as correlation-matrix |
| `POST /combine-presplit` | fastApiService | Fail | Fail | Fail | Fail | Fail | Plain fetch, no timeout, no retry, no keepalive |
| `POST /finalize-presplit` | fastApiService | Fail | Fail | Fail | Fail | Fail | Plain fetch, no timeout, no retry, no keepalive |
| `POST /documentation/get-data-insights` | fastApiService | Fail | Fail | Fail | Fail | Fail | No timeout/retry/keepalive observed |
| `POST /generate-knowledge-graph` | fastApiService | Fail | Fail | Fail | Fail | Fail | KG is long-running; no timeout/retry; relies on SSE stream |

---

## Job-start requests

*POST that queues async work and returns `job_id` immediately.*

**Gold standard:** short timeout (≤30s), retry-on-error (network/5xx), retry-on-timeout, idempotency key to prevent duplicate jobs.

| Endpoint | Client | Timeout | Retry error | Retry timeout | Backoff | Notes |
|----------|--------|---------|-------------|---------------|---------|-------|
| `POST /feature-transformation/start` | fastApiService | Fail | Fail | Fail | Fail | `fetchWithAutoRefresh`; no timeout/retry |
| `POST /auto-training/run` | fastApiService | Fail | Fail | Fail | Fail | `fetchWithAutoRefresh`; no timeout/retry |
| `POST /train-multiple-models` | fastApiService | Fail | Fail | Fail | Fail | `fetchWithAutoRefresh`; no timeout/retry |
| `POST /rfe/start` | fastApiService | Fail | Fail | Fail | Fail | `fetchWithAutoRefresh`; no timeout/retry |
| `POST /segment-training/run` | fastApiService | Fail | Fail | Fail | Fail | `fetchWithAutoRefresh`; no timeout/retry |
| `POST /segment-auto-training/run` | fastApiService | Fail | Fail | Fail | Fail | `fetchWithAutoRefresh`; no timeout/retry |
| `POST /auto-training/analyze/start` | fastApiService | Fail | Fail | Fail | Fail | `fetchWithAutoRefresh`; no timeout/retry |
| `POST /calculate-vif-correlation/start` | fastApiService | Fail | Fail | Fail | Fail | `fetchWithAutoRefresh`; no timeout/retry |
| `POST /segment-profiling/start` | fastApiService | Fail | Fail | Fail | Fail | `fetchWithAutoRefresh`; no timeout/retry |
| `POST /dataset-type-classification-by-id` | fastApiService | Fail | Fail | Fail | Fail | `fetchWithAutoRefresh`; no timeout/retry |

---

## Polling requests

*`GET /status/{job_id}` (or equivalent) on a timer to track async job progress.*

**Gold standard:** abort after N (e.g. 3) consecutive poll failures; reset the failure counter when a successful poll is received; exponential backoff between polls; surface a user-visible error on abort.

| Endpoint | Client | Max attempts | Abort on N consecutive fails | Reset counter on success | Backoff | Notes |
|----------|--------|--------------|------------------------------|--------------------------|---------|-------|
| `GET /feature-transformation/status/{id}` | fastApiService | Partial | Fail | Fail | Fail | `pollInsightJobUntilComplete`: 180 max, 2s interval; no abort-on-N-fail; no reset counter |
| `GET /auto-training/status/{id}` | fastApiService | Partial | Fail | Fail | Fail | `setInterval` fixed 3s; no N-fail abort; no counter reset on success |
| `GET /rfe/stream/{id}` (SSE) | fastApiService | Partial | Fail | Fail | Fail | SSE with `AbortController`; no fail-counter or N-abort logic |
| `GET /train-multiple-models/status/{id}` | fastApiService | Partial | Fail | Fail | Fail | `setInterval` fixed 3s; no N-fail abort; no counter reset on success |
| `GET /segment-training/status/{id}` | fastApiService | Partial | Fail | Fail | Fail | `setInterval` pattern; no N-fail abort; no counter reset on success |
| `GET /segment-auto-training/status/{id}` | fastApiService | Partial | Fail | Fail | Fail | Same pattern |
| `GET /auto-training/analyze/status/{id}` | fastApiService | Partial | Fail | Fail | Fail | `pollInsightJobUntilComplete`: 180 max; no N-fail abort |
| `GET /calculate-vif-correlation/status/{id}` | fastApiService | Partial | Fail | Fail | Fail | Same |
| `GET /segment-profiling/status/{id}` | fastApiService | Partial | Fail | Fail | Fail | No dedicated poll; relies on consumer; no N-fail logic |
| `GET /dataset-type-classification/status/{id}` | fastApiService | Partial | Fail | Fail | Fail | Same |
| `GET /insights/jobs/status/{id}` | fastApiService | Pass | Fail | Fail | Fail | 180 max attempts is bounded; no N-fail abort; no counter reset |
| `GET /knowledge-graph-progress/{id}` | fastApiService | Partial | Fail | Fail | Fail | `setInterval` pattern; no N-fail abort; no counter reset on success |

### Critical polling gap

No polling loop in the codebase implements: **abort after N consecutive HTTP errors, reset counter on a good response.** The current approach either loops until a terminal job state or exhausts a **total** attempt cap — it cannot distinguish a transient network blip from a permanently broken server.

---

## Other request types

*Chunked upload, SSE streams, QC steps, external APIs, credit risk.*

| Endpoint / group | Client | Category | Retry error | Retry timeout | Backoff | Notes |
|------------------|--------|----------|-------------|---------------|---------|-------|
| `PATCH /upload-chunked/{id}` (chunk) | fastApiService | Chunked upload | Pass | Partial | Partial | Retry ×3 per chunk, linear 1.5s/3s (not full exponential). No timeout per chunk |
| `POST /upload-chunked/init` | fastApiService | Chunked upload | Fail | Fail | Fail | Single plain fetch, no retry, no timeout |
| `POST /upload-chunked/{id}/finalize` | fastApiService | Chunked upload | Fail | Fail | Fail | Single plain fetch, no retry, no timeout |
| `GET /auto-training/stream/{id}` (SSE) | fastApiService | SSE stream | Fail | Fail | Fail | `EventSource` opened; no reconnect/retry on error; `AbortController` cancels |
| `GET /rfe/stream/{id}` (SSE) | fastApiService | SSE stream | Fail | Fail | Fail | Fetch SSE (not `EventSource`); no reconnect on error |
| `POST /validate-unique-ids-by-id` | fastApiService | Validation | Pass | Pass | Partial | Retry ×3, linear 3s/6s; `AbortSignal` supported; 60s timeout per attempt |
| `POST /qc/next-step` | fastApiService | QC step | Fail | Fail | Fail | `fetchWithAutoRefresh`; no timeout/retry |
| `POST /qc/regenerate-code` | fastApiService | QC step | Fail | Fail | Fail | `fetchWithAutoRefresh`; no timeout/retry |
| CreditRiskAPI calls | creditRiskApi | Credit risk | Fail | Fail | Fail | Separate service; no retry/timeout; different base URL (`localhost:3001`) |
| FRED / FMP / Moonshot / Gemini calls | apiServices | External | Fail | Fail | Fail | Direct fetch; no retry, no timeout; separate service instances |

---

## Gold standard checklist

**Roll-up:** Pass 0 · Partial 4 · Fail 11 (of 15)

| Standard | Status | Detail |
|----------|--------|--------|
| Single API client for all MIDAS backend calls | Fail | Three clients: `apiInterceptor`, `FastAPIService`, `creditRiskApi`. `fastApiService` and `apiInterceptor` overlap and differ in behaviour. |
| Consistent timeout on all non-streaming calls | Fail | Only `analyzeDataset` and `uploadDataset` have dynamic timeouts. Most calls have no timeout. |
| Retry-on-error for short-lived calls (min 2 attempts) | Fail | Only `analyzeDataset` and `validateUniqueIdsById` retry. GET-only short-lived calls have zero retry. |
| Retry-on-timeout for short-lived calls | Fail | Same gap as retry-on-error; no timeout means no retry-on-timeout is possible. |
| Exponential backoff on retries | Partial | `analyzeDataset` and `validateUniqueIdsById` use linear delay (3s, 6s). Chunked upload uses 1.5s × attempt. None use true exponential + jitter. |
| 401 token-refresh + retry on every call | Partial | `apiInterceptor` and `fetchWithAutoRefresh` do one refresh+retry. Plain `fetch()` calls (many in `fastApiService`) have no 401 handling. |
| Polling: N consecutive failures → abort + surface error | Fail | No poll loop aborts on N consecutive failures. `pollInsightJobUntilComplete` aborts on total attempts, not consecutive errors. |
| Polling: reset failure counter on a successful poll | Fail | Not implemented; no failure counter to reset. |
| Polling: exponential/jitter backoff between polls | Fail | Polling uses fixed intervals (2s or 3s). No backoff, no jitter. |
| Long-lived calls: keepalive during processing | Partial | Keepalive for upload and `analyzeDataset`. Not for partition-preview, exclusion-preview, chat, training kicks, variable-review. |
| Long-lived calls: `AbortController` / cancellation | Partial | Training jobs have cancel + `AbortController`. Most other long-lived calls have no cancellation path. |
| SSE: `EventSource` reconnect on error | Fail | Auto-training stream uses raw `EventSource` with no reconnect; RFE stream uses fetch-based SSE with no reconnect. |
| All API calls go through one base-URL config | Partial | `fastApiService` and `apiInterceptor` resolve `VITE_BASE_URL`; `creditRiskApi` hardcodes `localhost:3001`; external APIs hardcode prod URLs. |
| RFC 7807 Problem Details error format on client | Fail | Backend returns FastAPI `{ detail: ... }`. Client parses `errorData.detail` but does not follow RFC 7807; no structured error type on client. |
| Idempotency tokens on mutating retried calls | Fail | No idempotency-key header on retried POSTs; retry after a network glitch may duplicate the operation. |

---

## Priority fix recommendations

### P0 — Consolidate to one client

Migrate all `fastApiService` plain-`fetch` calls to either `apiInterceptor` or a single enriched wrapper with: `AbortController` timeout, 401-refresh, retry-with-backoff. Wire `creditRiskApi` to `VITE_BASE_URL` instead of a non-standard base URL.

### P0 — Add timeout to every call

Wrap every `fetch` in an `AbortController` with tiered timeout: 10s short-lived, 30s job-starts, dynamic (file-size scaled) for uploads/analysis, no hard cap for SSE streams (or a very large cap with explicit UX).

### P1 — Robust polling with N-fail abort

Introduce a reusable `pollJobUntilDone(jobId, opts)` helper that: (a) tracks consecutive HTTP errors and aborts after 3 consecutive failures; (b) resets the counter on any successful 200 poll; (c) uses exponential backoff with jitter (e.g. `2s * 1.5^n + random 0–500ms`).

### P1 — Retry on error + exponential backoff

Short-lived: 3 attempts, exp backoff 500ms → 1s → 2s. Long-lived (partition-preview, chat, variable-review, exclusion-preview): 2 attempts, 3s → 6s. Add jitter. Retry only on 5xx or network errors, never on 4xx (except 429 with `Retry-After`).

### P1 — Idempotency keys for job-start POSTs

Add client-generated `X-Idempotency-Key: <uuid>` to all job-start POSTs (`auto-training/run`, `train-multiple-models`, `feature-transformation/start`, `rfe/start`, etc.) so a retried POST cannot create a duplicate job.

### P2 — SSE reconnect strategy

Replace raw `EventSource` with a wrapper that reconnects with exponential backoff, max reconnect attempts (e.g. 5), surfaces “stream lost” to the UI, and falls back to HTTP polling after max reconnects.

### P2 — Keepalive for all long-lived calls

Extend `startKeepalive` / `stopKeepalive` to cover partition-preview, exclusion-preview, variable-review, chat, and any other call expected to exceed ~60s.

### P2 — Structured error type (RFC 7807)

Introduce a `MidasApiError` (or equivalent) carrying `status`, `code`, and `detail`. All client error paths should throw or return this type so the UI can render structured messages.

---

## Source files and date

Audit derived from: `frontend/src/services/fastApiService.ts`, `frontend/src/services/apiInterceptor.ts`, `frontend/src/services/apiServices.ts`, `frontend/src/services/creditRiskApi.ts`, and `backend/docs/API_REFERENCE.md`.

Document generated May 2026.

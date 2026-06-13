# MIDAS Backend – API Reference

A scannable reference for every HTTP endpoint in the MIDAS FastAPI backend (`bu-analytics-gen-ai-midas/backend`). Each endpoint below has its own block with **Headers** and **Request Body** explicitly listed.

- **Source files:** `app/api/routes.py`, `app/api/auth_routes.py`, `app/api/cognito_routes.py`, `app/api/project_routes.py`, `app/api/documentation_routes.py`, `app/api/rfe_routes.py`, `main.py`
- **Pydantic schemas:** `app/models/schemas.py` (+ inline `class …Request(BaseModel)` blocks in `documentation_routes.py`)

---

## 1. Base URLs

| Environment | Base URL | Notes |
|---|---|---|
| **Local dev** | `http://localhost:8000` | What `start.py` / `run_server.py` boots; `stress_tests/.env` -> `BASE_URL` defaults to this; `frontend/.env.example` -> `VITE_BASE_URL=http://localhost:8000`. |
| **Dev (deployed)** | `https://exldecision-ai-dev.exlservice.com` | EXL ALB hostname for the deployed dev stack. Same hostname serves both the React SPA and the FastAPI backend behind path-based routing. Configured in `deploy/ecs-app/tfvars/dev.tfvars` -> `frontend_vite_base_url` and in `backend/.env` -> `CORS_ALLOW_ORIGINS` / `COGNITO_REDIRECT_URIS`. |

All endpoints are **prefixed with `/api/v1`** unless explicitly noted (only `/` and `/health` are unprefixed).

```text
# Examples
GET  http://localhost:8000/health
GET  http://localhost:8000/api/v1/datasets
POST https://exldecision-ai-dev.exlservice.com/api/v1/auth/cognito/exchange
```

---

## 2. Common Headers

The headers below apply across many endpoints. Each per-endpoint block in §5–§12 shows the **required** headers explicitly; assume the optional/observability headers in §2.2 may always be sent.

### 2.1 Authentication

| Header | Value | When |
|---|---|---|
| `Authorization` | `Bearer <internal_jwt>` | Required on every endpoint **except**: `/`, `/health`, `/api/v1/auth/login`, `/api/v1/auth/register`, `/api/v1/auth/cognito/login-url`, `/api/v1/auth/cognito/exchange`, `/api/v1/auth/cognito/refresh`. The token is the **internal MIDAS JWT** (HS256) returned by `/auth/cognito/exchange` or `/auth/login` — NOT the Cognito access token. |
| `Content-Type` | `application/json` | All `POST`/`PUT` endpoints whose body is JSON. |
| `Content-Type` | `multipart/form-data` | All endpoints that use `UploadFile` or `Form(...)` — explicitly flagged per endpoint. |
| `Accept` | `text/event-stream` | Required for the SSE streaming endpoints (`/auto-training/stream/*`, `/rfe/stream/*`, `/knowledge-graph-stream/*`). |

### 2.2 Optional / observability headers

| Header | Purpose |
|---|---|
| `X-Request-ID` | Correlation ID; if absent, `request_id_middleware` generates a UUID and echoes it back in the response `X-Request-ID`. |
| `traceparent` | W3C distributed tracing header. Parsed into `trace_id` / `span_id` for structured logs. |
| `X-Trace-Id`, `X-Span-Id` | Fallback tracing headers if `traceparent` is absent. |
| `X-Tenant-ID` | Tenant correlator; truncated to 128 chars and added to log lines. |
| `X-Session-Id` | Allowed by CORS; mostly informational (the server uses the `sid` claim inside the JWT). |
| `x-llm-chat-model`, `x-llm-kg-model`, `x-llm-embedding-model` | Allowed by CORS for legacy clients; current routing is tag-based via env, so these are no-ops. |

### 2.3 Cookies (Cognito flow only)

| Cookie | Set by | Used by |
|---|---|---|
| `cg_login` (HttpOnly, path `/api/v1/auth/cognito`) | `GET /auth/cognito/login-url` | `POST /auth/cognito/exchange` (binds state + nonce + PKCE verifier hash). |
| `midas_cg_rt` (HttpOnly, path `/api/v1/auth/cognito`) | `POST /auth/cognito/exchange` | `POST /auth/cognito/refresh`, `POST /auth/cognito/logout`. Holds the **Cognito** refresh token. |
| `refresh_token` (legacy) | `POST /auth/login` | `POST /auth/refresh`. Only when `ENABLE_LEGACY_PASSWORD_LOGIN=true`. |

### 2.4 Server response headers

- `X-Request-ID` — echoed back on every response.
- CORS headers honour `CORS_ALLOW_ORIGINS` from `backend/.env` (must list every frontend origin; `*` is silently ignored when cookies are in play).
- Rate limiting: standard `Retry-After` on `429`; tunable via `RATE_LIMIT_*` env vars.

---

## 3. Conventions

- Body shapes use TypeScript-style notation: `?` = optional, `[]` = list, `{...}` = object.
- Endpoints suffixed `*/start` return `{ job_id: str }` immediately. Pair with `*/status/{job_id}` (poll) or `*/stream/{job_id}` (SSE) and `*/cancel/{job_id}` where available.
- SSE stream endpoints bypass the request-logging and request-id middleware.
- Errors follow FastAPI's default shape: `{ "detail": "..." }` with appropriate `4xx`/`5xx` status codes.
- "★ Critical" markers identify high-traffic/blocking flows worth prioritising for monitoring & load-testing.

---

## 4. ★ Critical APIs (cheat-sheet)

| # | Method | Path | Why it matters |
|---|---|---|---|
| 1 | POST | `/api/v1/auth/cognito/exchange` | Token mint after Cognito login |
| 2 | POST | `/api/v1/auth/cognito/refresh` | Silent refresh of internal JWT |
| 3 | POST | `/api/v1/upload` | Dataset ingestion |
| 4 | GET  | `/api/v1/datasets` | Dataset list (every screen) |
| 5 | GET  | `/api/v1/datasets/{dataset_id}/stats` | Dataset header / overview |
| 6 | GET  | `/api/v1/datasets/{dataset_id}/eda-snapshot` | EDA tab |
| 7 | POST | `/api/v1/generate-knowledge-graph` | KG (long-running) |
| 8 | POST | `/api/v1/chat` | Agentic chat |
| 9 | POST | `/api/v1/insights/correlation-matrix` | Correlation tab |
| 10 | POST | `/api/v1/insights/iv-analysis` | IV tab |
| 11 | POST | `/api/v1/insights/vif-analysis-dedicated` | VIF tab |
| 12 | POST | `/api/v1/feature-transformation/start` | Feature engineering |
| 13 | POST | `/api/v1/auto-training/run` | Auto-training kickoff |
| 14 | GET  | `/api/v1/auto-training/stream/{job_id}` | Auto-training progress |
| 15 | POST | `/api/v1/train-multiple-models` | Manual training kickoff |
| 16 | POST | `/api/v1/rfe/start` | RFE kickoff |
| 17 | GET  | `/api/v1/rfe/stream/{job_id}` | RFE progress |
| 18 | POST | `/api/v1/rfe/finalize` | RFE HITL finalize |
| 19 | GET  | `/api/v1/model-evaluation/{model_id}` | Model evaluation tab |
| 20 | POST | `/api/v1/documentation/get-data-insights` | Documentation block |

Full per-endpoint blocks (Headers + Request Body) follow.

---

## 5. Root & Health

### `GET /`

Liveness ping → `{"message":"MIDAS API is running"}`.

- **Headers:** none required.
- **Request Body:** none.

### `GET /health`

Health check including vector-store init status and document count.

- **Headers:** none required.
- **Request Body:** none.

---

## 6. Authentication – Legacy (`/api/v1/auth`)

Disabled unless `ENABLE_LEGACY_PASSWORD_LOGIN=true`. Auth header **not** required for `register` / `login` / `refresh`.

### `POST /api/v1/auth/register`

Register a new local user.

- **Headers:** `Content-Type: application/json`
- **Request Body** (JSON):
  ```json
  {
    "username": "string (3-50)",
    "full_name": "string (1-100)",
    "email": "string? (≤100)",
    "password": "string (≥6)",
    "is_active": true
  }
  ```

### `POST /api/v1/auth/login`

Username/password login → `{ access_token, refresh_token, session_id, user }`. Sets `refresh_token` cookie.

- **Headers:** `Content-Type: application/json`
- **Request Body** (JSON):
  ```json
  { "username": "string", "password": "string" }
  ```

### `GET /api/v1/auth/me`

Authenticated user's profile.

- **Headers:** `Authorization: Bearer <jwt>`
- **Request Body:** none.

### `GET /api/v1/auth/users`

List users.

- **Headers:** `Authorization: Bearer <jwt>`
- **Query:** `?skip=0&limit=100`
- **Request Body:** none.

### `PUT /api/v1/auth/users/{user_id}`

Update a user.

- **Headers:** `Authorization: Bearer <jwt>`, `Content-Type: application/json`
- **Path:** `user_id` (int)
- **Request Body** (JSON):
  ```json
  { "full_name": "string?", "email": "string?", "is_active": "bool?" }
  ```

### `DELETE /api/v1/auth/users/{user_id}`

Delete a user (cannot self-delete).

- **Headers:** `Authorization: Bearer <jwt>`
- **Path:** `user_id` (int)
- **Request Body:** none.

### `POST /api/v1/auth/refresh`

Exchange a refresh token for a new access token.

- **Headers:** `Content-Type: application/json` (or `Cookie: refresh_token=…`)
- **Request Body** (JSON):
  ```json
  { "refresh_token": "string?" }
  ```
  If body is empty/null, the server reads the `refresh_token` cookie.

### `POST /api/v1/auth/logout`

Invalidate the server session and revoke this user's refresh tokens.

- **Headers:** `Authorization: Bearer <jwt>`
- **Request Body:** none.

### `POST /api/v1/auth/verify-token`

Validate an access token and return user info → `{ valid, user }`.

- **Headers:** `Authorization: Bearer <jwt>`
- **Request Body:** none.

---

## 7. Authentication – Cognito SSO (`/api/v1/auth/cognito`)

`exchange`, `refresh`, `login-url` do **not** require a bearer token but DO require the relevant cookies.

### `GET /api/v1/auth/cognito/login-url` ★

Build the Cognito authorize URL + set `cg_login` cookie. Returns `{ authorize_url, state, nonce }`.

- **Headers:** none required.
- **Query:** `?vhash=<sha256-hex-of-PKCE-verifier>` (64 hex chars, required)
- **Request Body:** none.

### `POST /api/v1/auth/cognito/exchange` ★

Exchange auth code + PKCE verifier for tokens; mint internal JWT; set `midas_cg_rt` cookie.

- **Headers:** `Content-Type: application/json`, `Cookie: cg_login=…` (set by `/login-url`)
- **Request Body** (JSON, `extra="forbid"`):
  ```json
  {
    "code": "string (1-4096)",
    "state": "string (1-512)",
    "code_verifier": "string (43-128, RFC 7636)",
    "redirect_uri": "string (1-2048)"
  }
  ```

### `POST /api/v1/auth/cognito/refresh` ★

Silent refresh: mint a new internal app JWT using the `midas_cg_rt` cookie. Rotates Redis `sid`.

- **Headers:** `Cookie: midas_cg_rt=…`
- **Request Body:** none.

### `POST /api/v1/auth/cognito/logout`

Revoke Cognito refresh token (RFC 7009), invalidate session, clear cookies, return Cognito logout URL.

- **Headers:** `Authorization: Bearer <jwt>`, `Cookie: midas_cg_rt=…`
- **Request Body:** none.

### `POST /api/v1/auth/cognito/logout-everywhere`

Same as `/logout` (placeholder for future per-session revocation).

- **Headers:** `Authorization: Bearer <jwt>`, `Cookie: midas_cg_rt=…`
- **Request Body:** none.

---

## 8. Projects (`/api/v1/projects`)

All require `Authorization: Bearer <jwt>`.

### `POST /api/v1/projects`

Create a project for the current user.

- **Headers:** `Authorization: Bearer <jwt>`, `Content-Type: application/json`
- **Request Body** (JSON):
  ```json
  { "name": "string (1-100)", "description": "string? (≤500)" }
  ```

### `GET /api/v1/projects`

List the user's projects (paginated).

- **Headers:** `Authorization: Bearer <jwt>`
- **Query:** `?skip=0&limit=100`
- **Request Body:** none.

### `GET /api/v1/projects/{project_id}`

Get a project (ownership-checked).

- **Headers:** `Authorization: Bearer <jwt>`
- **Path:** `project_id` (str/uuid)
- **Request Body:** none.

### `PUT /api/v1/projects/{project_id}`

Update a project.

- **Headers:** `Authorization: Bearer <jwt>`, `Content-Type: application/json`
- **Path:** `project_id` (str/uuid)
- **Request Body** (JSON):
  ```json
  { "name": "string?", "description": "string?" }
  ```

### `DELETE /api/v1/projects/{project_id}`

Delete a project.

- **Headers:** `Authorization: Bearer <jwt>`
- **Path:** `project_id` (str/uuid)
- **Request Body:** none.

---

## 9. Dataset Upload & Lifecycle (`/api/v1`)

All require `Authorization: Bearer <jwt>`.

### 9.1 Ingestion

#### `POST /api/v1/upload` ★

Upload a CSV dataset, profile it, and register it in the dataset manager.

- **Headers:** `Authorization: Bearer <jwt>`, `Content-Type: multipart/form-data`
- **Form fields:**
  - `file` (UploadFile) — single CSV (or omit and use `files[]`)
  - `files[]` (UploadFile[]) — multiple files; required when `merge_validation=true`
  - `merge_validation` (str, optional) — `"true"` to merge validation files
  - `target_variable` (str, **required**)
  - `target_variable_type` (str, **required**) — `"Numerical" | "Categorical"`
  - `unique_id_combinations` (str, **required**) — JSON array, e.g. `'["id_col"]'`
  - `data_dictionary` (str, optional) — inline text
  - `data_dictionary_file` (UploadFile, optional)
  - `problem_statement` (str, optional)
  - `segmentation_variable` (str, optional)
  - `sample_identifier_variable` (str, optional)
  - `has_sampling_variable` (str, optional) — boolean string
  - `sampling_variable` (str, optional)
  - `split_ratio` (str, optional) — float as string, e.g. `"0.7"`
  - `initial_scope` (str, optional)
  - `split_configuration` (str, optional) — JSON string
  - `exclusion_rules` (str, optional) — JSON string
  - `variables_to_remove` (str, optional) — JSON string
  - `partition_role` (str, optional) — `"train" | "test" | "validation"`

#### `POST /api/v1/validate-unique-ids`

Validate that an uploaded file has unique row IDs.

- **Headers:** `Authorization: Bearer <jwt>`, `Content-Type: multipart/form-data`
- **Form fields:**
  - `file` (UploadFile, **required**)
  - `unique_id_combinations` (str, **required**) — JSON array

#### `POST /api/v1/combine-presplit`

Combine train/test/validation files uploaded separately into one logical dataset.

- **Headers:** `Authorization: Bearer <jwt>`, `Content-Type: multipart/form-data`
- **Form fields:** `files[]` (UploadFile[], **required**), partition labels per file (`partition_roles` JSON), `target_variable`, `unique_id_combinations`

#### `POST /api/v1/finalize-presplit`

Persist the combined pre-split dataset and trigger profiling.

- **Headers:** `Authorization: Bearer <jwt>`, `Content-Type: multipart/form-data`
- **Form fields:** combined-file metadata + same target/uniqueness fields as `/upload`.

#### `POST /api/v1/analyze-dataset`

Lightweight server-side profile of a CSV/Parquet without registering it.

- **Headers:** `Authorization: Bearer <jwt>`, `Content-Type: multipart/form-data`
- **Form fields:** `file` (UploadFile, **required**)

### 9.2 QC, Partitioning, Exclusions, Variable Review

#### `POST /api/v1/generate-qc-template/{template_type}`

Generate a downloadable QC checklist template.

- **Headers:** `Authorization: Bearer <jwt>`, `Content-Type: application/json`
- **Path:** `template_type` (str) — `"csv" | "excel" | "json"`
- **Request Body** (JSON): template-specific fields (columns, treatments).

#### `POST /api/v1/partition-preview`

Preview train/test/validation row counts for a freshly uploaded file.

- **Headers:** `Authorization: Bearer <jwt>`, `Content-Type: multipart/form-data`
- **Form fields:**
  - `file` (UploadFile, **required**)
  - `split_configuration` (str, **required**) — JSON
  - `target_variable` (str, **required**)
  - `exclusion_rules` (str, optional) — JSON

#### `POST /api/v1/partition-preview-by-id`

Preview partition splits for an already-registered dataset.

- **Headers:** `Authorization: Bearer <jwt>`, `Content-Type: multipart/form-data`
- **Form fields:** `dataset_id` (str), `split_configuration` (JSON str), `target_variable`, `exclusion_rules?` (JSON str)

#### `POST /api/v1/exclusion-preview`

Preview row exclusions for a freshly uploaded file.

- **Headers:** `Authorization: Bearer <jwt>`, `Content-Type: multipart/form-data`
- **Form fields:** `file` (UploadFile), `exclusion_groups` (JSON str), `target_variable`

#### `POST /api/v1/exclusion-preview-by-id`

Preview row exclusions for a registered dataset.

- **Headers:** `Authorization: Bearer <jwt>`, `Content-Type: multipart/form-data`
- **Form fields:** `dataset_id`, `exclusion_groups` (JSON str), `target_variable`

#### `POST /api/v1/variable-review/preview`

Preview variables flagged for removal.

- **Headers:** `Authorization: Bearer <jwt>`, `Content-Type: multipart/form-data`
- **Form fields:** `file` (UploadFile), threshold fields per `VariableReviewRequest`

#### `POST /api/v1/variable-review/run`

Execute the configured variable-review rules and return diagnostics.

- **Headers:** `Authorization: Bearer <jwt>`, `Content-Type: application/json`
- **Request Body** (JSON):
  ```json
  {
    "dataset_id": "string",
    "target_col": "string",
    "sample_id_col": "string?",
    "weight_col": "string?",
    "auc_threshold": 0.70,
    "near_perfect_auc_threshold": 0.95,
    "correlation_threshold": 0.70,
    "missingness_diff_threshold": 0.10,
    "leaker_correlation_threshold": 0.85
  }
  ```

#### `POST /api/v1/variable-review/apply`

Persist variable removals back to the dataset config.

- **Headers:** `Authorization: Bearer <jwt>`, `Content-Type: application/json`
- **Request Body** (JSON):
  ```json
  { "dataset_id": "string", "variables_to_remove": ["string", "..."] }
  ```

### 9.3 Dataset Catalog

#### `GET /api/v1/datasets` ★

List datasets for the current user.

- **Headers:** `Authorization: Bearer <jwt>`
- **Request Body:** none.

#### `GET /api/v1/datasets/{dataset_id}/stats` ★

Summary stats + column metadata.

- **Headers:** `Authorization: Bearer <jwt>`
- **Path:** `dataset_id` (str)
- **Request Body:** none.

#### `DELETE /api/v1/datasets/{dataset_id}`

Delete a dataset and its artifacts.

- **Headers:** `Authorization: Bearer <jwt>`
- **Path:** `dataset_id` (str)
- **Request Body:** none.

#### `GET /api/v1/datasets/{dataset_id}/raw-data`

Paginated raw rows for previews.

- **Headers:** `Authorization: Bearer <jwt>`
- **Path:** `dataset_id` (str)
- **Query:** `?page=1&page_size=100`
- **Request Body:** none.

#### `GET /api/v1/datasets/{dataset_id}/export`

Download the dataset (CSV/parquet) post-treatments.

- **Headers:** `Authorization: Bearer <jwt>`
- **Path:** `dataset_id` (str)
- **Query:** `?format=csv|parquet`
- **Request Body:** none.

#### `PUT /api/v1/datasets/{dataset_id}/config`

Update partition / target / weight / treatment config for a dataset.

- **Headers:** `Authorization: Bearer <jwt>`, `Content-Type: application/json`
- **Path:** `dataset_id` (str)
- **Request Body** (JSON):
  ```json
  {
    "partition": { "split_method": "...", "split_ratio": 0.7 },
    "target_variable": "string?",
    "weight_variable": "string?",
    "treatments": { "...": "..." }
  }
  ```

### 9.4 Column-Level Insights

#### `GET /api/v1/datasets/{dataset_id}/column-distribution/{column_name}`

Histogram / value-counts for a single column.

- **Headers:** `Authorization: Bearer <jwt>`
- **Path:** `dataset_id`, `column_name` (str)
- **Request Body:** none.

#### `GET /api/v1/datasets/{dataset_id}/column-distribution-by-scope/{column_name}`

Same as above, partition-filtered.

- **Headers:** `Authorization: Bearer <jwt>`
- **Path:** `dataset_id`, `column_name` (str)
- **Query:** `?scope=entire|train|test|validation`
- **Request Body:** none.

#### `POST /api/v1/datasets/{dataset_id}/classify-variables`

Async LLM-driven variable classification (numerical/categorical/identifier/etc.).

- **Headers:** `Authorization: Bearer <jwt>`, `Content-Type: application/json`
- **Path:** `dataset_id` (str)
- **Request Body** (JSON):
  ```json
  { "overrides": { "<column>": "Numerical|Categorical|Identifier" } }
  ```

#### `GET /api/v1/datasets/{dataset_id}/classify-variables/status`

Poll status of the classification job.

- **Headers:** `Authorization: Bearer <jwt>`
- **Path:** `dataset_id` (str)
- **Request Body:** none.

#### `POST /api/v1/datasets/{dataset_id}/column-insights`

LLM-generated narrative insights for selected columns.

- **Headers:** `Authorization: Bearer <jwt>`, `Content-Type: application/json`
- **Path:** `dataset_id` (str)
- **Request Body** (JSON):
  ```json
  { "columns": ["string", "..."], "context": "string?" }
  ```

#### `POST /api/v1/datasets/{dataset_id}/cross-algorithm-recommendation`

Recommend which algorithms suit this dataset shape.

- **Headers:** `Authorization: Bearer <jwt>`, `Content-Type: application/json`
- **Path:** `dataset_id` (str)
- **Request Body** (JSON):
  ```json
  {
    "problem_type": "classification",
    "candidates": [{ "...": "..." }],
    "lr_digest": [{ "...": "..." }]
  }
  ```

#### `GET /api/v1/datasets/{dataset_id}/column-info`

Detailed column-info payload.

- **Headers:** `Authorization: Bearer <jwt>`
- **Path:** `dataset_id` (str)
- **Request Body:** none.

#### `GET /api/v1/datasets/{dataset_id}/column-info-by-scope`

Column-info filtered by partition scope.

- **Headers:** `Authorization: Bearer <jwt>`
- **Path:** `dataset_id` (str)
- **Query:** `?scope=entire|train|test|validation`
- **Request Body:** none.

### 9.5 Knowledge Graph

#### `POST /api/v1/generate-knowledge-graph` ★

Build a knowledge graph for the dataset (queues background work).

- **Headers:** `Authorization: Bearer <jwt>`, `Content-Type: application/json`
- **Request Body** (JSON):
  ```json
  { "dataset_id": "string" }
  ```

#### `GET /api/v1/knowledge-graph-progress/{dataset_id}`

Poll progress percentage of KG generation.

- **Headers:** `Authorization: Bearer <jwt>`
- **Path:** `dataset_id` (str)
- **Request Body:** none.

#### `GET /api/v1/knowledge-graph-stream/{dataset_id}`

SSE stream of live KG generation progress.

- **Headers:** `Authorization: Bearer <jwt>`, `Accept: text/event-stream`
- **Path:** `dataset_id` (str)
- **Request Body:** none.

### 9.6 Data Quality Score (DQS)

#### `GET /api/v1/datasets/{dataset_id}/dqs`

Composite DQS + per-dimension breakdown.

- **Headers:** `Authorization: Bearer <jwt>`
- **Path:** `dataset_id` (str)
- **Request Body:** none.

#### `GET /api/v1/datasets/{dataset_id}/dqs-by-scope`

DQS scoped to train/test/validation.

- **Headers:** `Authorization: Bearer <jwt>`
- **Path:** `dataset_id` (str)
- **Query:** `?scope=entire|train|test|validation`
- **Request Body:** none.

#### `POST /api/v1/datasets/{dataset_id}/dqs-recommendations`

LLM-driven remediation recommendations for low-DQS columns.

- **Headers:** `Authorization: Bearer <jwt>`, `Content-Type: application/json`
- **Path:** `dataset_id` (str)
- **Request Body** (JSON):
  ```json
  { "context": "string?", "focus_columns": ["string"] }
  ```

### 9.7 Downloads & Comparisons

#### `GET /api/v1/datasets/{dataset_id}/download-processed`

Download the post-treatment processed dataset.

- **Headers:** `Authorization: Bearer <jwt>`
- **Path:** `dataset_id` (str)
- **Request Body:** none.

#### `GET /api/v1/datasets/{dataset_id}/download-column-stats`

Download per-column statistics as Excel.

- **Headers:** `Authorization: Bearer <jwt>`
- **Path:** `dataset_id` (str)
- **Request Body:** none.

#### `GET /api/v1/datasets/{dataset_id}/compare-column-stats`

Compare column stats across train/test/validation.

- **Headers:** `Authorization: Bearer <jwt>`
- **Path:** `dataset_id` (str)
- **Query:** `?scope=entire|train|test|validation`
- **Request Body:** none.

### 9.8 Duplicates & EDA Snapshot

#### `POST /api/v1/datasets/{dataset_id}/identify-duplicates`

Find duplicate rows by configurable key set.

- **Headers:** `Authorization: Bearer <jwt>`, `Content-Type: application/json`
- **Path:** `dataset_id` (str)
- **Request Body** (JSON):
  ```json
  { "key_columns": ["string"], "include_preview": true }
  ```

#### `POST /api/v1/datasets/{dataset_id}/remove-duplicates`

Remove identified duplicates and persist.

- **Headers:** `Authorization: Bearer <jwt>`, `Content-Type: application/json`
- **Path:** `dataset_id` (str)
- **Request Body** (JSON):
  ```json
  { "key_columns": ["string"], "keep": "first" }
  ```

#### `GET /api/v1/datasets/{dataset_id}/eda-snapshot` ★

Cached EDA snapshot (counts/missing/dtypes) per scope.

- **Headers:** `Authorization: Bearer <jwt>`
- **Path:** `dataset_id` (str)
- **Query:** `?scope=entire|train|test|validation`
- **Request Body:** none.

### 9.9 User Knowledge & Misc

#### `POST /api/v1/user-knowledge/upload`

Upload user-provided domain-knowledge files.

- **Headers:** `Authorization: Bearer <jwt>`, `Content-Type: multipart/form-data`
- **Form fields:** `dataset_id` (str), `file` (UploadFile)

#### `POST /api/v1/user-knowledge/preferences`

Persist user preference flags for knowledge usage.

- **Headers:** `Authorization: Bearer <jwt>`, `Content-Type: multipart/form-data`
- **Form fields:** `dataset_id` (str), preference flag fields (`use_exl_expertise`, `use_uploaded_files`, ...)

#### `POST /api/v1/vector-store/reinitialize`

Force-rebuild the in-process vector store.

- **Headers:** `Authorization: Bearer <jwt>`
- **Request Body:** none.

---

## 10. Chat / Modelling Agent (`/api/v1`)

All require `Authorization: Bearer <jwt>`.

### 10.1 Configuration & Scope

#### `GET /api/v1/llm-config`

Resolved LLM routing configuration (chat / kg / embedding tags).

- **Headers:** `Authorization: Bearer <jwt>`
- **Request Body:** none.

#### `POST /api/v1/dataset/scope`

Switch the active dataframe scope.

- **Headers:** `Authorization: Bearer <jwt>`, `Content-Type: application/json`
- **Request Body** (JSON):
  ```json
  {
    "dataset_id": "string",
    "scope": "train|test|validation|entire|dev|hold",
    "seed": 42,
    "ratio": 0.7,
    "sampling_variable": "string?"
  }
  ```

#### `GET /api/v1/keepalive`

Heartbeat for SSE/long-running clients.

- **Headers:** `Authorization: Bearer <jwt>`
- **Request Body:** none.

### 10.2 Chat & Code Execution

#### `POST /api/v1/chat` ★

Main agentic chat – ReAct-style with tool calls.

- **Headers:** `Authorization: Bearer <jwt>`, `Content-Type: application/json`
- **Request Body** (JSON, `ChatRequest`):
  ```json
  {
    "query": "string",
    "dataset_id": "string",
    "agent_context": "data_insight|modelling|data_quality|null",
    "qc_mode": "auto|manual|null",
    "treatment_sequence": ["string", "..."],
    "qc_templates": { "...": "..." },
    "qc_ui_selections": { "...": "..." }
  }
  ```

#### `GET /api/v1/chat/{dataset_id}/history`

Return chat history for a dataset.

- **Headers:** `Authorization: Bearer <jwt>`
- **Path:** `dataset_id` (str)
- **Request Body:** none.

#### `DELETE /api/v1/chat/{dataset_id}/reset`

Clear the chat / message state for a dataset.

- **Headers:** `Authorization: Bearer <jwt>`
- **Path:** `dataset_id` (str)
- **Request Body:** none.

#### `GET /api/v1/chat/states`

List all chat states for the user.

- **Headers:** `Authorization: Bearer <jwt>`
- **Request Body:** none.

#### `POST /api/v1/execute-code`

Sandboxed Python execution against a dataset's dataframe.

- **Headers:** `Authorization: Bearer <jwt>`, `Content-Type: multipart/form-data`
- **Form fields:** `dataset_id` (str), `code` (str)

### 10.3 QC Treatments

#### `POST /api/v1/qc/next-step`

Ask the agent for the next QC treatment to apply.

- **Headers:** `Authorization: Bearer <jwt>`, `Content-Type: application/json`
- **Request Body** (JSON):
  ```json
  {
    "dataset_id": "string",
    "action": "apply|skip",
    "treatment_type": "string",
    "code": "string?"
  }
  ```

#### `POST /api/v1/qc/skip-treatment`

Skip the current QC treatment (forces `action="skip"` server-side).

- **Headers:** `Authorization: Bearer <jwt>`, `Content-Type: application/json`
- **Request Body** (JSON): same shape as `/qc/next-step`.

#### `POST /api/v1/qc/regenerate-code`

Regenerate code for the current QC treatment from UI selections.

- **Headers:** `Authorization: Bearer <jwt>`, `Content-Type: application/json`
- **Request Body** (JSON):
  ```json
  {
    "dataset_id": "string",
    "treatment_type": "string",
    "selections": { "<key>": "<value>" }
  }
  ```

#### `POST /api/v1/update-custom-treatments`

Apply user-customised QC treatments.

- **Headers:** `Authorization: Bearer <jwt>`, `Content-Type: application/json`
- **Request Body** (JSON):
  ```json
  {
    "dataset_id": "string",
    "custom_treatments": { "<category-or-index>": "<treatment text>" }
  }
  ```

### 10.4 Variable / Insight Analyses

#### `POST /api/v1/insights/bivariate/all`

Run bivariate analysis across all candidate variables.

- **Headers:** `Authorization: Bearer <jwt>`, `Content-Type: multipart/form-data`
- **Form fields:** `dataset_id` (str), `target_variable` (str), `selected_variables` (JSON str, optional)

#### `GET /api/v1/insights/bivariate/{dataset_id}/variable/{variable_name}`

Bivariate analysis for one variable.

- **Headers:** `Authorization: Bearer <jwt>`
- **Path:** `dataset_id`, `variable_name`
- **Query:** `?target_variable=<name>`
- **Request Body:** none.

#### `POST /api/v1/insights/vif-analysis`

Generic VIF analysis (legacy form).

- **Headers:** `Authorization: Bearer <jwt>`, `Content-Type: multipart/form-data`
- **Form fields:** `dataset_id`, `target_variable`, `max_columns?` (int)

#### `POST /api/v1/insights/vif-analysis-dedicated` ★

Dedicated VIF analysis used by the EDA UI.

- **Headers:** `Authorization: Bearer <jwt>`, `Content-Type: multipart/form-data`
- **Form fields:** `dataset_id` (str), `target_variable` (str), `max_columns?` (int)

#### `POST /api/v1/insights/correlation-ratio-analysis`

η² (correlation-ratio) analysis for cat–num pairs.

- **Headers:** `Authorization: Bearer <jwt>`, `Content-Type: multipart/form-data`
- **Form fields:** `dataset_id`, `target_variable`

#### `POST /api/v1/insights/correlation/analyze`

Run correlation analysis (Pearson/Spearman) on selected vars.

- **Headers:** `Authorization: Bearer <jwt>`, `Content-Type: multipart/form-data`
- **Form fields:** `dataset_id`, `target_variable`, `correlation_threshold?=0.05`, `correlation_types?` (JSON str array, default `["pearson","spearman"]`)

#### `GET /api/v1/insights/correlation/{dataset_id}/variable/{variable_name}`

Per-variable correlation drilldown.

- **Headers:** `Authorization: Bearer <jwt>`
- **Path:** `dataset_id`, `variable_name`
- **Query:** `?target_variable=<name>`
- **Request Body:** none.

#### `GET /api/v1/insights/correlation/{dataset_id}/heatmap`

Numerical correlation heatmap image (base64 PNG).

- **Headers:** `Authorization: Bearer <jwt>`
- **Path:** `dataset_id`
- **Query:** `?target_variable=<name>`
- **Request Body:** none.

#### `GET /api/v1/insights/correlation/{dataset_id}/heatmap/categorical`

Categorical correlation heatmap image.

- **Headers:** `Authorization: Bearer <jwt>`
- **Path:** `dataset_id`
- **Query:** `?target_variable=<name>`
- **Request Body:** none.

#### `POST /api/v1/insights/correlation-matrix` ★

Full correlation matrix payload.

- **Headers:** `Authorization: Bearer <jwt>`, `Content-Type: multipart/form-data`
- **Form fields:** `dataset_id` (str), `target_variable` (str)

#### `POST /api/v1/insights/iv-analysis` ★

Information-Value (IV) per feature.

- **Headers:** `Authorization: Bearer <jwt>`, `Content-Type: multipart/form-data`
- **Form fields:** `dataset_id` (str), `target_variable` (str), `bins?=10` (int)

### 10.5 Segmentation

#### `POST /api/v1/run-segmentation`

Run a manually-configured segmentation.

- **Headers:** `Authorization: Bearer <jwt>`, `Content-Type: application/json`
- **Request Body** (JSON, `SegmentationRequest`):
  ```json
  {
    "dataset_id": "string",
    "variables": ["string", "..."],
    "method": "cart|chaid",
    "target_variable": "string?",
    "max_depth": 4,
    "min_samples_leaf": 25,
    "min_segment_size_ratio": 0.05,
    "max_segments": 8
  }
  ```

#### `POST /api/v1/run-auto-segmentation`

LLM-assisted automatic segmentation.

- **Headers:** `Authorization: Bearer <jwt>`, `Content-Type: application/json`
- **Request Body** (JSON, `AutoSegmentationRequest`): same as above minus `variables`.

#### `GET /api/v1/dataset-preview/{dataset_id}`

Preview rows of the base dataset.

- **Headers:** `Authorization: Bearer <jwt>`
- **Path:** `dataset_id`
- **Query:** `?rows=100`
- **Request Body:** none.

#### `GET /api/v1/segmented-dataset-preview/{dataset_id}`

Preview rows after segmentation.

- **Headers:** `Authorization: Bearer <jwt>`
- **Path:** `dataset_id`
- **Query:** `?rows=100&segment_id=<id>`
- **Request Body:** none.

#### `POST /api/v1/segment-profiling/start`

Async segment-profiling job; returns `job_id`.

- **Headers:** `Authorization: Bearer <jwt>`, `Content-Type: application/json`
- **Request Body** (JSON): `{ "dataset_id": "string", "segments": [{ "...": "..." }] }`

#### `GET /api/v1/segment-profiling/status/{job_id}`

Poll segment-profiling job.

- **Headers:** `Authorization: Bearer <jwt>`
- **Path:** `job_id`
- **Request Body:** none.

### 10.6 Dataset-Type Classification

#### `POST /api/v1/dataset-type-classification-by-id`

Classify dataset (credit-risk, propensity, etc.) using an existing `dataset_id` after upload — returns `job_id` (no second CSV upload).

- **Headers:** `Authorization: Bearer <jwt>`, `Content-Type: application/json`
- **Request Body** (JSON): `{ "dataset_id": "string", "target_variable": "string", "target_variable_type": "string" }`

#### `GET /api/v1/dataset-type-classification/status/{job_id}`

Poll dataset-type classification job.

- **Headers:** `Authorization: Bearer <jwt>`
- **Path:** `job_id`
- **Request Body:** none.

### 10.7 Feature Engineering

#### `POST /api/v1/feature-transformation/start` ★

Async start of the feature-transformation pipeline.

- **Headers:** `Authorization: Bearer <jwt>`, `Content-Type: multipart/form-data`
- **Form fields:**
  - `dataset_id` (str, **required**)
  - `plan_json` (str, **required**) — JSON array, e.g. `'[{"variable":"income","methods":["WOE","LOG","OHE"]}]'`
  - `target_variable` (str, optional)
  - `weight_variable` (str, optional)

#### `GET /api/v1/feature-transformation/status/{job_id}`

Poll feature-transformation job.

- **Headers:** `Authorization: Bearer <jwt>`
- **Path:** `job_id`
- **Request Body:** none.

### 10.8 Global / Manual Training

#### `POST /api/v1/train-global-model`

Train a single global model (sync wrapper around the auto pipeline).

- **Headers:** `Authorization: Bearer <jwt>`, `Content-Type: application/json`
- **Request Body** (JSON, `GlobalModelTrainingRequest`):
  ```json
  {
    "dataset_id": "string",
    "algorithm": "random_forest|gradient_boosting|logistic_regression",
    "k_folds": 5,
    "target_variable": "string?",
    "selected_variables": ["string"]
  }
  ```

#### `GET /api/v1/train-global-model/status/{job_id}`

Poll global-model training.

- **Headers:** `Authorization: Bearer <jwt>`
- **Path:** `job_id`
- **Request Body:** none.

#### `GET /api/v1/model-codebook/{algorithm}`

Source code template for an algorithm.

- **Headers:** `Authorization: Bearer <jwt>`
- **Path:** `algorithm` (str)
- **Request Body:** none.

#### `POST /api/v1/auto-train-model`

Trigger automated training with provided params (lightweight wrapper).

- **Headers:** `Authorization: Bearer <jwt>`, `Content-Type: application/json`
- **Request Body** (JSON):
  ```json
  {
    "dataset_id": "string",
    "target_column": "string",
    "target_metric": "string",
    "target_value": 0.85,
    "independent_variables": ["string"],
    "max_runtime_secs": 30
  }
  ```

#### `POST /api/v1/detect-problem-type`

Detect classification vs regression from the target column.

- **Headers:** `Authorization: Bearer <jwt>`, `Content-Type: application/json`
- **Request Body** (JSON):
  ```json
  { "dataset_id": "string", "target_column": "string" }
  ```

#### `POST /api/v1/get-available-variables`

List variables eligible for selection.

- **Headers:** `Authorization: Bearer <jwt>`, `Content-Type: application/json`
- **Request Body** (JSON):
  ```json
  { "dataset_id": "string" }
  ```

#### `POST /api/v1/validate-variable-selection`

Validate a user-selected variable list.

- **Headers:** `Authorization: Bearer <jwt>`, `Content-Type: application/json`
- **Request Body** (JSON):
  ```json
  {
    "dataset_id": "string",
    "target_column": "string",
    "independent_variables": ["string"]
  }
  ```

#### `POST /api/v1/training/lock-variables`

Lock a set of must-include variables for downstream training.

- **Headers:** `Authorization: Bearer <jwt>`, `Content-Type: application/json`
- **Request Body** (JSON):
  ```json
  {
    "dataset_id": "string",
    "target_column": "string",
    "selected_variables": ["string"],
    "locked_variables": ["string"],
    "mode": "auto|manual",
    "variable_analysis": { "...": "..." }
  }
  ```

#### `POST /api/v1/get-recommended-metrics`

Recommend optimization metrics given the problem type.

- **Headers:** `Authorization: Bearer <jwt>`, `Content-Type: application/json`
- **Request Body** (JSON):
  ```json
  { "problem_type": "classification|regression" }
  ```

#### `POST /api/v1/train-multiple-models` ★

Manual training: train N user-selected algorithms in the background.

- **Headers:** `Authorization: Bearer <jwt>`, `Content-Type: application/json`
- **Request Body** (JSON):
  ```json
  {
    "dataset_id": "string",
    "target_column": "string",
    "algorithms": ["xgboost", "lightgbm"],
    "independent_variables": ["string?"],
    "algorithm_params": { "<algo>": { "...": "..." } },
    "algorithm_param_ranges": { "<algo>": { "<param>": { "min": 0, "max": 1 } } },
    "optimization_method": "random|optuna|grid",
    "target_metric": "auc",
    "cv_folds": 5,
    "optuna_trials": 30,
    "early_stopping_rounds": 10,
    "max_iterations": 3,
    "weight_variable": "string?",
    "locked_variables": ["string"],
    "lr_backward_elimination": { "vif_threshold": 5, "p_value_threshold": 0.05 }
  }
  ```

#### `POST /api/v1/model-training/lr-backward-elimination`

On-demand §7.2 LR backward elimination.

- **Headers:** `Authorization: Bearer <jwt>`, `Content-Type: application/json`
- **Request Body** (JSON):
  ```json
  {
    "dataset_id": "string",
    "target_column": "string",
    "independent_variables": ["string"],
    "locked_variables": ["string"],
    "weight_variable": "string?",
    "vif_threshold": 5,
    "p_value_threshold": 0.05,
    "segment_id": "string?",
    "segment_column": "string?"
  }
  ```

#### `GET /api/v1/train-multiple-models/status/{job_id}`

Poll manual-training job.

- **Headers:** `Authorization: Bearer <jwt>`
- **Path:** `job_id`
- **Request Body:** none.

#### `POST /api/v1/train-multiple-models/cancel/{job_id}`

Cancel a manual-training job.

- **Headers:** `Authorization: Bearer <jwt>`
- **Path:** `job_id`
- **Request Body:** none.

### 10.9 Segment Training

#### `POST /api/v1/detect-segments`

Detect whether a segmentation column exists in the dataset.

- **Headers:** `Authorization: Bearer <jwt>`, `Content-Type: application/json`
- **Request Body** (JSON):
  ```json
  { "dataset_id": "string" }
  ```

#### `POST /api/v1/segment-training/run`

Train models per segment, returns `job_id`.

- **Headers:** `Authorization: Bearer <jwt>`, `Content-Type: application/json`
- **Request Body** (JSON):
  ```json
  {
    "dataset_id": "string",
    "target_column": "string",
    "independent_variables": ["string"],
    "algorithms": ["xgboost"],
    "algorithm_params": { "<algo>": { "...": "..." } },
    "algorithm_param_ranges": { "...": "..." },
    "optimization_method": "random",
    "target_metric": "auc",
    "cv_folds": 5,
    "optuna_trials": 30,
    "early_stopping_rounds": 10,
    "max_iterations": 5,
    "weight_variable": "string?",
    "locked_variables": ["string"],
    "lr_backward_elimination": { "...": "..." }
  }
  ```

#### `GET /api/v1/segment-training/status/{job_id}`

Poll segment-training job.

- **Headers:** `Authorization: Bearer <jwt>`
- **Path:** `job_id`
- **Request Body:** none.

#### `POST /api/v1/segment-training/cancel/{job_id}`

Cancel segment-training job.

- **Headers:** `Authorization: Bearer <jwt>`
- **Path:** `job_id`
- **Request Body:** none.

#### `GET /api/v1/segment-training/{model_id}/results`

Per-segment training results.

- **Headers:** `Authorization: Bearer <jwt>`
- **Path:** `model_id`
- **Query:** `?segment_id=<id>`
- **Request Body:** none.

#### `GET /api/v1/segment-training/{model_id}/history`

Per-segment training history.

- **Headers:** `Authorization: Bearer <jwt>`
- **Path:** `model_id`
- **Query:** `?segment_id=<id>`
- **Request Body:** none.

#### `GET /api/v1/segment-training/{model_id}/compare`

Compare multiple segments side-by-side.

- **Headers:** `Authorization: Bearer <jwt>`
- **Path:** `model_id`
- **Query:** `?segments=<csv-of-ids>`
- **Request Body:** none.

#### `GET /api/v1/segment-training/{model_id}/unified-results`

Unified roll-up across segments.

- **Headers:** `Authorization: Bearer <jwt>`
- **Path:** `model_id`
- **Request Body:** none.

#### `GET /api/v1/segment-training/{model_id}/screen`

Screen-friendly per-algo per-segment payload.

- **Headers:** `Authorization: Bearer <jwt>`
- **Path:** `model_id`
- **Query:** `?segment_id=<id>&algorithm=<algo>`
- **Request Body:** none.

#### `GET /api/v1/segment-training/preview`

Preview the segments configuration before training.

- **Headers:** `Authorization: Bearer <jwt>`
- **Query:** `?dataset_id=<id>`
- **Request Body:** none.

### 10.10 VIF / Correlation Pre-flight

#### `POST /api/v1/calculate-vif-correlation/start`

Async VIF + correlation pre-flight; returns `job_id`.

- **Headers:** `Authorization: Bearer <jwt>`, `Content-Type: application/json`
- **Request Body** (JSON):
  ```json
  {
    "dataset_id": "string",
    "target_column": "string",
    "independent_variables": ["string"]
  }
  ```

#### `GET /api/v1/calculate-vif-correlation/status/{job_id}`

Poll VIF/correlation job.

- **Headers:** `Authorization: Bearer <jwt>`
- **Path:** `job_id`
- **Request Body:** none.

### 10.11 Model Export & Logs

#### `GET /api/v1/export-model/{model_id}`

Export a trained model (optionally with artifacts).

- **Headers:** `Authorization: Bearer <jwt>`
- **Path:** `model_id`
- **Query:** `?include_artifacts=false`
- **Request Body:** none.

#### `GET /api/v1/training-logs/{model_id}`

Fetch training logs for a model.

- **Headers:** `Authorization: Bearer <jwt>`
- **Path:** `model_id`
- **Request Body:** none.

#### `GET /api/v1/models/{model_id}/download-artifacts`

Download zipped artifacts (pickle, metadata, code).

- **Headers:** `Authorization: Bearer <jwt>`
- **Path:** `model_id`
- **Request Body:** none.

### 10.12 Auto-Training Pipeline

#### `POST /api/v1/auto-training/analyze`

Sync dataset analysis prep step.

- **Headers:** `Authorization: Bearer <jwt>`, `Content-Type: application/json`
- **Request Body** (JSON):
  ```json
  { "dataset_id": "string", "target_column": "string" }
  ```

#### `POST /api/v1/auto-training/analyze/start`

Async dataset analysis; returns `job_id`.

- **Headers:** `Authorization: Bearer <jwt>`, `Content-Type: application/json`
- **Request Body** (JSON):
  ```json
  { "dataset_id": "string", "target_column": "string" }
  ```

#### `GET /api/v1/auto-training/analyze/status/{job_id}`

Poll dataset-analysis job.

- **Headers:** `Authorization: Bearer <jwt>`
- **Path:** `job_id`
- **Request Body:** none.

#### `POST /api/v1/auto-training/select-variables`

Auto variable-selection step.

- **Headers:** `Authorization: Bearer <jwt>`, `Content-Type: application/json`
- **Request Body** (JSON):
  ```json
  {
    "dataset_id": "string",
    "target_column": "string",
    "variable_analysis": { "...": "..." },
    "problem_type": "classification"
  }
  ```

#### `POST /api/v1/auto-training/select-algorithms`

Auto algorithm-selection step.

- **Headers:** `Authorization: Bearer <jwt>`, `Content-Type: application/json`
- **Request Body** (JSON):
  ```json
  {
    "dataset_id": "string",
    "problem_type": "classification|regression",
    "dataset_size": 100000,
    "num_features": 42,
    "feature_types": { "numerical": 30, "categorical": 12 }
  }
  ```

#### `GET /api/v1/auto-training/meea-status/{dataset_id}`

MEEA (model-evaluation/explainability) readiness for a dataset.

- **Headers:** `Authorization: Bearer <jwt>`
- **Path:** `dataset_id`
- **Request Body:** none.

#### `POST /api/v1/auto-training/run` ★

Run the full auto-training pipeline; returns `job_id`.

- **Headers:** `Authorization: Bearer <jwt>`, `Content-Type: application/json`
- **Request Body** (JSON):
  ```json
  {
    "dataset_id": "string",
    "target_column": "string",
    "selected_variables": ["string"],
    "locked_variables": ["string"],
    "selection_mode": "auto|manual",
    "selected_algorithms": ["string"],
    "weight_variable": "string?"
  }
  ```

#### `GET /api/v1/auto-training/status/{job_id}`

Poll auto-training job.

- **Headers:** `Authorization: Bearer <jwt>`
- **Path:** `job_id`
- **Request Body:** none.

#### `GET /api/v1/auto-training/stream/{job_id}` ★

SSE stream of auto-training progress.

- **Headers:** `Authorization: Bearer <jwt>`, `Accept: text/event-stream`
- **Path:** `job_id`
- **Request Body:** none.

#### `POST /api/v1/auto-training/cancel/{job_id}`

Cancel auto-training.

- **Headers:** `Authorization: Bearer <jwt>`
- **Path:** `job_id`
- **Request Body:** none.

#### `POST /api/v1/auto-training/select-best-model`

Pick the best model from a finished run with reasoning.

- **Headers:** `Authorization: Bearer <jwt>`, `Content-Type: application/json`
- **Request Body** (JSON):
  ```json
  {
    "training_results": { "...": "..." },
    "selection_criteria": { "...": "..." }
  }
  ```

### 10.13 Segment Auto-Training

#### `POST /api/v1/segment-auto-training/run`

Auto-train per segment; returns `job_id`.

- **Headers:** `Authorization: Bearer <jwt>`, `Content-Type: application/json`
- **Request Body** (JSON): same shape as `/auto-training/run` plus segment fields.

#### `GET /api/v1/segment-auto-training/status/{job_id}`

Poll segment auto-training.

- **Headers:** `Authorization: Bearer <jwt>`
- **Path:** `job_id`
- **Request Body:** none.

#### `POST /api/v1/segment-auto-training/cancel/{job_id}`

Cancel segment auto-training.

- **Headers:** `Authorization: Bearer <jwt>`
- **Path:** `job_id`
- **Request Body:** none.

#### `GET /api/v1/segment-auto-training/{model_id}/unified-results`

Unified roll-up across segments.

- **Headers:** `Authorization: Bearer <jwt>`
- **Path:** `model_id`
- **Request Body:** none.

#### `GET /api/v1/segment-auto-training/{model_id}/segment/{segment_id}`

Results for one segment.

- **Headers:** `Authorization: Bearer <jwt>`
- **Path:** `model_id`, `segment_id`
- **Request Body:** none.

#### `GET /api/v1/export-segment-model/{model_id}/{segment_id}`

Download zipped per-segment best model (pickle + JSON).

- **Headers:** `Authorization: Bearer <jwt>`
- **Path:** `model_id`, `segment_id`
- **Request Body:** none.

#### `GET /api/v1/get-codebook/{training_mode}/{training_type}`

Source code for a given (mode, type) training combo.

- **Headers:** `Authorization: Bearer <jwt>`
- **Path:** `training_mode`, `training_type`
- **Request Body:** none.

### 10.14 Model Evaluation

#### `GET /api/v1/model-evaluation/{model_id}` ★

Full evaluation payload (metrics + explainability).

- **Headers:** `Authorization: Bearer <jwt>`
- **Path:** `model_id`
- **Query:** `?include_explainability=true`
- **Request Body:** none.

#### `GET /api/v1/model-evaluation/{model_id}/phase/{phase_num}`

Evaluation slice for a given phase.

- **Headers:** `Authorization: Bearer <jwt>`
- **Path:** `model_id`, `phase_num` (int)
- **Request Body:** none.

#### `GET /api/v1/model-evaluation/list/all`

List every evaluated model.

- **Headers:** `Authorization: Bearer <jwt>`
- **Request Body:** none.

#### `GET /api/v1/model-evaluation/list/by-dataset`

List evaluated models for a dataset.

- **Headers:** `Authorization: Bearer <jwt>`
- **Query:** `?dataset_id=<id>`
- **Request Body:** none.

#### `GET /api/v1/model-evaluation/{model_id}/samples`

Sample-level predictions.

- **Headers:** `Authorization: Bearer <jwt>`
- **Path:** `model_id`
- **Query:** `?sample_type=<type>&limit=100`
- **Request Body:** none.

#### `POST /api/v1/model-evaluation/compare`

Compare multiple models head-to-head.

- **Headers:** `Authorization: Bearer <jwt>`, `Content-Type: application/json`
- **Request Body** (JSON):
  ```json
  { "model_ids": ["string", "..."], "metrics": ["auc", "f1"] }
  ```

#### `GET /api/v1/model-evaluation/{model_id}/performance`

Performance metrics block only.

- **Headers:** `Authorization: Bearer <jwt>`
- **Path:** `model_id`
- **Request Body:** none.

#### `GET /api/v1/model-evaluation/{model_id}/feature-importance`

Feature importance block.

- **Headers:** `Authorization: Bearer <jwt>`
- **Path:** `model_id`
- **Request Body:** none.

#### `GET /api/v1/model-evaluation/{model_id}/granular-accuracy`

Granular accuracy (decile / score-band).

- **Headers:** `Authorization: Bearer <jwt>`
- **Path:** `model_id`
- **Request Body:** none.

#### `GET /api/v1/model-evaluation/{model_id}/granular-accuracy/by-segments`

Granular accuracy split by segment.

- **Headers:** `Authorization: Bearer <jwt>`
- **Path:** `model_id`
- **Query:** `?segment_column=<col>&segments=<csv>`
- **Request Body:** none.

#### `GET /api/v1/model-evaluation/{model_id}/error-patterns`

Error-pattern analysis.

- **Headers:** `Authorization: Bearer <jwt>`
- **Path:** `model_id`
- **Request Body:** none.

#### `GET /api/v1/model-evaluation/{model_id}/explainability`

SHAP / explainability block.

- **Headers:** `Authorization: Bearer <jwt>`
- **Path:** `model_id`
- **Request Body:** none.

#### `GET /api/v1/model-evaluation/{model_id}/pdp-data`

Partial-dependence plot data.

- **Headers:** `Authorization: Bearer <jwt>`
- **Path:** `model_id`
- **Query:** `?data_source=test|train`
- **Request Body:** none.

#### `GET /api/v1/model-evaluation/{model_id}/prediction-confidence`

Prediction-confidence distribution.

- **Headers:** `Authorization: Bearer <jwt>`
- **Path:** `model_id`
- **Request Body:** none.

#### `DELETE /api/v1/model-evaluation/{model_id}`

Delete an evaluation record.

- **Headers:** `Authorization: Bearer <jwt>`
- **Path:** `model_id`
- **Request Body:** none.

#### `POST /api/v1/model-evaluation/{original_model_id}/evaluate-pruned`

Re-evaluate a pruned variant of a model.

- **Headers:** `Authorization: Bearer <jwt>`, `Content-Type: application/json`
- **Path:** `original_model_id`
- **Request Body** (JSON):
  ```json
  { "pruned_features": ["string"], "label": "string?" }
  ```

#### `POST /api/v1/model-evaluation/evaluate-existing/{model_id}`

Re-evaluate an existing model from its stored JSON.

- **Headers:** `Authorization: Bearer <jwt>`
- **Path:** `model_id`
- **Request Body:** none.

#### `POST /api/v1/model-evaluation/evaluate-all-existing`

Bulk re-evaluation of all existing models.

- **Headers:** `Authorization: Bearer <jwt>`
- **Request Body:** none.

#### `POST /api/v1/model-evaluation/{model_id}/recalculate-explainability`

Recompute SHAP/PDP on train or test.

- **Headers:** `Authorization: Bearer <jwt>`, `Content-Type: application/json`
- **Path:** `model_id`
- **Request Body** (JSON):
  ```json
  { "data_source": "train|test" }
  ```

#### `GET /api/v1/model-evaluation/{model_id}/chat-summary`

LLM-narrated summary of a model's evaluation.

- **Headers:** `Authorization: Bearer <jwt>`
- **Path:** `model_id`
- **Request Body:** none.

#### `GET /api/v1/segmentation-model-evaluation/segments/{dataset_id}`

Available segment IDs for model evaluation.

- **Headers:** `Authorization: Bearer <jwt>`
- **Path:** `dataset_id`
- **Request Body:** none.

#### `GET /api/v1/segmentation-model-evaluation/{dataset_id}/{segment_id}`

Per-segment model evaluation listing.

- **Headers:** `Authorization: Bearer <jwt>`
- **Path:** `dataset_id`, `segment_id`
- **Request Body:** none.

---

## 11. RFE – Recursive Feature Elimination (`/api/v1/rfe`)

Step 3 of the modelling pipeline. All require `Authorization: Bearer <jwt>`.

### `POST /api/v1/rfe/start` ★

Enqueue a new RFE job for `(dataset_id, target, working_set)`.

- **Headers:** `Authorization: Bearer <jwt>`, `Content-Type: application/json`
- **Request Body** (JSON, `RfeStartRequest`):
  ```json
  {
    "dataset_id": "string",
    "target": "string",
    "working_set": {
      "locked": ["string"],
      "screened": ["string"],
      "precomputed_metrics": {
        "<var>": {
          "iv": 0.12,
          "orig_vif": 1.4,
          "abs_corr": 0.3,
          "missing_pct": 0.0,
          "signed_corr": 0.3
        }
      }
    },
    "weight_col": "string?",
    "segment_id": "string?  (accepted but ignored — Step 3 always uses whole train)"
  }
  ```

### `GET /api/v1/rfe/status/{job_id}`

Snapshot of job status, current iteration, best CV-AUC.

- **Headers:** `Authorization: Bearer <jwt>`
- **Path:** `job_id`
- **Request Body:** none.

### `GET /api/v1/rfe/stream/{job_id}` ★

SSE stream of iteration ticks + final result.

- **Headers:** `Authorization: Bearer <jwt>`, `Accept: text/event-stream`
- **Path:** `job_id`
- **Request Body:** none.

### `POST /api/v1/rfe/cancel/{job_id}`

Set the cancel flag on a running job.

- **Headers:** `Authorization: Bearer <jwt>`
- **Path:** `job_id`
- **Request Body:** none.

### `GET /api/v1/rfe/result/{job_id}`

Final RFE result rows (retained / dropped / metrics).

- **Headers:** `Authorization: Bearer <jwt>`
- **Path:** `job_id`
- **Request Body:** none.

### `POST /api/v1/rfe/finalize` ★

HITL gate – persist final feature set + monotone constraints for Step 5.

- **Headers:** `Authorization: Bearer <jwt>`, `Content-Type: application/json`
- **Request Body** (JSON, `RfeFinalizeRequest`):
  ```json
  {
    "job_id": "string",
    "overrides": {
      "include": ["string"],
      "exclude": ["string"]
    },
    "monotone": { "<var>": -1 }
  }
  ```
  `monotone` values must be `-1`, `0`, or `1`.

### `GET /api/v1/rfe/monotone/{dataset_id}`

Read-only Step-5 pickup of finalized features + monotone map.

- **Headers:** `Authorization: Bearer <jwt>`
- **Path:** `dataset_id`
- **Request Body:** none.

---

## 12. Documentation Generation (`/api/v1/documentation`)

LLM-narrated artifacts assembled into the model documentation pack. All require `Authorization: Bearer <jwt>` and `Content-Type: application/json`.

### `POST /api/v1/documentation/generate-data-summary`

Narrative dataset summary section.

- **Headers:** `Authorization: Bearer <jwt>`, `Content-Type: application/json`
- **Request Body** (JSON):
  ```json
  { "columns": ["string"], "data_dictionary": "string?", "model_objective": "string?" }
  ```

### `POST /api/v1/documentation/generate-data-quality-summary`

Data-quality summary section.

- **Headers:** `Authorization: Bearer <jwt>`, `Content-Type: application/json`
- **Request Body** (JSON):
  ```json
  {
    "metrics": {
      "emptyColumns": 0,
      "constantColumns": 0,
      "...": "..."
    },
    "recommendations": ["string"],
    "totalRows": 0,
    "totalColumns": 0
  }
  ```

### `POST /api/v1/documentation/generate-target-definition`

Target-variable definition narrative.

- **Headers:** `Authorization: Bearer <jwt>`, `Content-Type: application/json`
- **Request Body** (JSON):
  ```json
  {
    "target_variable": "string",
    "data_dictionary": "string?",
    "columns": ["string"],
    "problem_statement": "string?"
  }
  ```

### `POST /api/v1/documentation/generate-model-objective`

Model-objective narrative.

- **Headers:** `Authorization: Bearer <jwt>`, `Content-Type: application/json`
- **Request Body** (JSON):
  ```json
  {
    "project_description": "string?",
    "problem_statement": "string?",
    "data_summary": "string?",
    "target_variable_name": "string?",
    "target_definition": "string?"
  }
  ```

### `POST /api/v1/documentation/generate-monotonicity-summary`

Monotonicity-constraint summary section.

- **Headers:** `Authorization: Bearer <jwt>`, `Content-Type: application/json`
- **Request Body** (JSON):
  ```json
  { "models": [{ "...monotonicity metrics": "..." }] }
  ```

### `POST /api/v1/documentation/calculate-event-rate`

Event rate (positive class %) per partition.

- **Headers:** `Authorization: Bearer <jwt>`, `Content-Type: application/json`
- **Request Body** (JSON):
  ```json
  { "dataset_id": "string", "target_variable": "string" }
  ```

### `POST /api/v1/documentation/get-sampling-plan`

Compute the sampling plan numbers.

- **Headers:** `Authorization: Bearer <jwt>`, `Content-Type: application/json`
- **Request Body** (JSON):
  ```json
  { "dataset_id": "string", "target_variable": "string" }
  ```

### `POST /api/v1/documentation/generate-sampling-plan-writeup`

Narrative writeup of the sampling plan.

- **Headers:** `Authorization: Bearer <jwt>`, `Content-Type: application/json`
- **Request Body** (JSON):
  ```json
  { "sampling_plan": { "...": "..." } }
  ```

### `POST /api/v1/documentation/generate-model-validation-writeup`

Narrative model-validation writeup.

- **Headers:** `Authorization: Bearer <jwt>`, `Content-Type: application/json`
- **Request Body** (JSON):
  ```json
  { "model_validation": { "...": "..." }, "data_summary": "string?" }
  ```

### `POST /api/v1/documentation/get-model-performance`

Model performance block for the doc.

- **Headers:** `Authorization: Bearer <jwt>`, `Content-Type: application/json`
- **Request Body** (JSON):
  ```json
  {
    "model_id": "string",
    "dataset_id": "string",
    "data_dictionary": "string?",
    "variable_categories": { "<feature>": "<category>" },
    "category_colors": { "<category>": "<color-hex>" }
  }
  ```

### `POST /api/v1/documentation/generate-segmentation-understanding`

Narrative segmentation-understanding section.

- **Headers:** `Authorization: Bearer <jwt>`, `Content-Type: application/json`
- **Request Body** (JSON):
  ```json
  {
    "data_summary": "string",
    "segments": [{ "...": "..." }],
    "segment_sizes": [0],
    "segment_proportions": [0.0],
    "event_rates": [0.0],
    "iv_report": { "...": "..." }
  }
  ```

### `POST /api/v1/documentation/get-quality-check-plan`

Quality-check plan block.

- **Headers:** `Authorization: Bearer <jwt>`, `Content-Type: application/json`
- **Request Body** (JSON):
  ```json
  { "dataset_id": "string" }
  ```

### `POST /api/v1/documentation/get-column-stats`

Column-stats block.

- **Headers:** `Authorization: Bearer <jwt>`, `Content-Type: application/json`
- **Request Body** (JSON):
  ```json
  { "dataset_id": "string" }
  ```

### `POST /api/v1/documentation/generate-quality-changes-writeup`

Narrative writeup of QC changes applied.

- **Headers:** `Authorization: Bearer <jwt>`, `Content-Type: application/json`
- **Request Body** (JSON):
  ```json
  {
    "quality_check_plan": { "...": "..." },
    "column_stats": [{ "...": "..." }]
  }
  ```

### `POST /api/v1/documentation/generate-feature-engineering-writeup`

Narrative feature-engineering writeup.

- **Headers:** `Authorization: Bearer <jwt>`, `Content-Type: application/json`
- **Request Body** (JSON):
  ```json
  {
    "transformed_variables": [{
      "new_variable_name": "string",
      "var_type": "string",
      "variable_definition": "string",
      "transformation_methods": "string"
    }]
  }
  ```

### `POST /api/v1/documentation/generate-decile-progression-writeup`

Decile-progression narrative.

- **Headers:** `Authorization: Bearer <jwt>`, `Content-Type: application/json`
- **Request Body** (JSON):
  ```json
  {
    "model_name": "string",
    "deciles": [{ "...": "..." }],
    "monotonicity_score": 0,
    "violations": [{ "fromDecile": 0, "toDecile": 0, "drop": 0 }]
  }
  ```

### `POST /api/v1/documentation/generate-ai-explainability-writeup`

Narrative AI-explainability writeup.

- **Headers:** `Authorization: Bearer <jwt>`, `Content-Type: application/json`
- **Request Body** (JSON):
  ```json
  {
    "beeswarm_data": [{ "...": "..." }],
    "waterfall_data": [{ "...": "..." }],
    "pdp_data": [{ "...": "..." }]
  }
  ```

### `POST /api/v1/documentation/get-transformed-variables`

List of transformed variables for the doc.

- **Headers:** `Authorization: Bearer <jwt>`, `Content-Type: application/json`
- **Request Body** (JSON):
  ```json
  { "dataset_id": "string" }
  ```

### `POST /api/v1/documentation/get-variable-analysis`

Variable-analysis block.

- **Headers:** `Authorization: Bearer <jwt>`, `Content-Type: application/json`
- **Request Body** (JSON):
  ```json
  { "dataset_id": "string" }
  ```

### `POST /api/v1/documentation/get-data-insights` ★

Auto-narrated data-insights block.

- **Headers:** `Authorization: Bearer <jwt>`, `Content-Type: application/json`
- **Request Body** (JSON):
  ```json
  { "dataset_id": "string" }
  ```

### `POST /api/v1/documentation/download`

Download the assembled documentation (Word/PDF).

- **Headers:** `Authorization: Bearer <jwt>`, `Content-Type: application/json`
- **Request Body** (JSON): the full assembled-documentation payload (sections + metadata) as a free-form object.

---

## 13. Quick Reference – cURL

### 13.1 Cognito login → bearer JWT

```bash
# 1. Get authorize URL + cg_login cookie
curl -s -c cookies.txt \
  "http://localhost:8000/api/v1/auth/cognito/login-url?vhash=<sha256-hex-of-pkce-verifier>"

# 2. After Cognito redirect, exchange the code
curl -s -b cookies.txt -c cookies.txt \
  -H "Content-Type: application/json" \
  -X POST http://localhost:8000/api/v1/auth/cognito/exchange \
  -d '{
    "code": "<auth_code>",
    "state": "<state_from_step_1>",
    "code_verifier": "<original_pkce_verifier>",
    "redirect_uri": "http://localhost:5173/auth/callback"
  }'
# → { "access_token": "eyJ...", "session_id": "...", "user": {...} }
```

### 13.2 Upload a dataset

```bash
curl -X POST http://localhost:8000/api/v1/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@./train.csv" \
  -F "target_variable=target" \
  -F "target_variable_type=Categorical" \
  -F 'unique_id_combinations=["id_col"]' \
  -F "problem_statement=Stress test"
# → { "success": true, "dataset_id": "...", "dataset_info": {...} }
```

### 13.3 Chat against a dataset

```bash
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Summarise the dataset",
    "dataset_id": "<id>",
    "agent_context": "data_insight"
  }'
```

### 13.4 Auto-training run + SSE stream

```bash
JOB=$(curl -s -X POST http://localhost:8000/api/v1/auto-training/run \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"dataset_id":"<id>","target_column":"target"}' | jq -r .job_id)

curl -N -H "Authorization: Bearer $TOKEN" \
  -H "Accept: text/event-stream" \
  http://localhost:8000/api/v1/auto-training/stream/$JOB
```

### 13.5 RFE start + finalize

```bash
JOB=$(curl -s -X POST http://localhost:8000/api/v1/rfe/start \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "dataset_id":"<id>",
    "target":"target",
    "working_set":{
      "locked":["age"],
      "screened":["income","balance","tenure"],
      "precomputed_metrics":{}
    }
  }' | jq -r .job_id)

curl -X POST http://localhost:8000/api/v1/rfe/finalize \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"job_id\":\"$JOB\",
    \"overrides\":{\"include\":[],\"exclude\":[]},
    \"monotone\":{\"income\":1,\"balance\":0}
  }"
```

---

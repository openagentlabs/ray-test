---
project_name: 'EXLDecision.AI'
user_name: 'EXLDecision.AI Team'
date: '2026-05-27'
sections_completed: ['technology_stack', 'language_rules', 'framework_rules', 'testing_rules', 'quality_rules', 'workflow_rules', 'anti_patterns', 'financial_data_rules']
status: 'complete'
rule_count: 140
optimized_for_llm: true
---

# Project Context for AI Agents

_This file contains critical rules and patterns that AI agents must follow when implementing code in this project. Focus on unobvious details that agents might otherwise miss._

---

## Quick Reference — Jump to What You Need

| Task | Section |
|---|---|
| Add a new API route | [Framework Rules — FastAPI](#framework-specific-rules--fastapi) |
| Add a new React page | [Framework Rules — React](#framework-specific-rules--react-frontend) |
| Log something in Python | [Language Rules — Python Logging](#language-specific-rules--python) |
| Add a new AWS secret | [Workflow — Secrets workflow](#development-workflow-rules) |
| Write a test | [Testing Rules](#testing-rules--backend-pytest) |
| Add a new LLM call | [Tech Stack — LLM Routing](#llm-routing-litellm) |
| Handle uploaded financial data | [Financial Data Rules](#financial-data-rules) |
| Add a new dependency | [Workflow — Dependencies](#development-workflow-rules) |
| Know what NOT to do | [Critical Anti-Patterns](#critical-anti-patterns--never-do-these) |
| Trigger a deployment | [Workflow — Deployment](#development-workflow-rules) |

---

> **Agent constraints — non-negotiable (read before anything else)**
> - No public AWS endpoints. All calls via PrivateLink / VPC endpoints. Egress via Transit Gateway `tgw-0ec391fa73943d562` only.
> - Python runtime is **pinned to 3.13.x** (see `backend/Dockerfile` — `python:3.13-slim`). Match local venv and CI to 3.13.
> - **AWS Cognito is the only auth path for new features.** `python-jose` / JWT is legacy only — do not use for new endpoints.
> - All credentials via **AWS Secrets Manager at runtime** — never in env vars injected at build time, never hardcoded in config or Helm values.
> - TypeScript `strict: true` enforced — no untyped props, no implicit `any`.
> - `ai_gateway/` is a **read-only git submodule** owned by an external team — never edit any file under it.
> - All intra-cluster calls use **Kubernetes service DNS** — never hardcode pod IPs or ALB hostnames.
> - FastAPI handlers must be **async** — never introduce blocking calls on the event loop.

---

## BMad workflow routing (four scenarios)

Use BMad skills in **fresh Cursor chats** per phase. Ground every run in this file plus `_bmad-output/project-context.md`. Business inputs go under `_bmad-output/intake/` (see `_bmad-output/intake/README.md`). Skill chains and prompts: `_bmad-output/How to use BMAD for each scenario.md`.

| Scenario | When to use | Primary code areas | Companion workflow |
|---|---|---|---|
| **1 — Model Lab feature** | New or improved capability inside Model Lab (`/models`, 9-step pipeline) | `frontend/src/pages/ModelBuilder.tsx`, `frontend/src/components/steps/`, `backend/app/api/`, `backend/app/services/` | **New features:** `bmad-prd` → `bmad-spec` → `bmad-create-epics-and-stories` → **`bmad-party-mode` (backlog)** → `bmad-create-story` → **`bmad-party-mode` (pre-dev per ST)** → `bmad-dev-story` → (`bmad-party-mode` pre-merge) → `bmad-code-review` → **tests green**. See `scenarios/01-requirements-traceability.md` |
| **2 — New platform module** | Standalone module; only platform dependency is login/logout (Cognito) | New top-level app folder or package; reuse `auth_routes` / Cognito patterns only | `bmad-create-architecture` → `bmad-spec` → `bmad-create-story` → `bmad-dev-story` → `bmad-code-review` → **tests green** |
| **3 — Bug resolution** | UI, deploy/readiness, backend formulas, security | Per bug domain | `bmad-investigate` → `bmad-quick-dev` / `bmad-dev-story` → `bmad-code-review` → **regression tests green**; deploy via Jenkins / `tf_validate` when infra |
| **4 — EKS scalability** | Multi-user large CSV (5 GB near-term, 20 GB target), 5→20 users/pods | S3 uploads, chunked APIs, Redis, Helm `deploy/ecs-app/helm/`, background jobs | `bmad-technical-research` → `bmad-create-architecture` → `bmad-dev-story` + verification checklist (see scenario 4 file) |

Invoke `bmad-help` when unsure of the next skill. Do not edit `ai_gateway/**`.

### Definition of done — scenarios 1–3 (mandatory test gate)

Work under scenarios **1**, **2**, or **3** is **not complete** until:

1. **Tests exist** — new or updated `backend/tests/` (pytest) and/or `frontend/src/**/*.test.tsx` (Vitest) covering the change; bug fixes require a **regression test**.
2. **Tests were executed** — agent or developer ran the commands in `_bmad-output/testing/scenario-test-gate.md` (or `run-scenario-tests.sh`).
3. **Tests passed** — full or scoped suite green; evidence pasted in chat, story, or PR.
4. **Review** — `bmad-code-review` completed (mandatory for security and financial-data paths).
5. **SME sign-off** — when tests cover formulas, ML training, or evaluation metrics, the developer shares `test-artifacts/sme-reviews/.../sme-review-package.md` with an SME and records **approved** in `sme-signoff.md` before the story is done (`_bmad-output/testing/sme-verification-gate.md`).

Optional: `bmad-qa-generate-e2e-tests` for additional API/E2E coverage. Team overrides: `_bmad/custom/bmad-dev-story.toml`, `bmad-create-story.toml`, `bmad-quick-dev.toml`.

### Scenario 1 — PRD adherence and task-by-task delivery (new features)

1. **Source of truth** — `_bmad-output/intake/01-model-lab/` and derived PRD/SPEC; business logic in code must match `REQ-*` / `CAP-*` IDs, not agent interpretation.
2. **Backlog before code** — `planning-artifacts/epics/<slug>/backlog.md` with epics, stories (`ST-*`), and subtasks (`SUB-*`) must be **human-approved** before any `bmad-dev-story`.
3. **One story per dev chat** — never implement multiple `ST-*` in one session; complete all `SUB-*` for that story.
4. **Traceability** — maintain `specs/spec-<slug>/traceability.md` and `planning-artifacts/epics/<slug>/traceability-matrix.md`; update on merge.
5. **Deviation** — if implementation cannot match PRD, stop and update PRD/spec — do not ship alternate logic.
6. **Party-mode gates** — after backlog approval and before each `bmad-dev-story`, run `bmad-party-mode` (PM + architect + dev [+ UX]) and save synthesis under `planning-artifacts/epics/<slug>/party-reviews/`. Do not code until **Proceed = yes**.

Full rules: `_bmad-output/scenarios/01-requirements-traceability.md`, `scenarios/01-model-lab-feature.md`.

---

## Large data, memory, and EKS scale (all scenarios — especially 4)

These constraints apply to any work touching uploads, datasets, caching, or pod sizing. They extend the anti-patterns below and MIDAS architecture rules.

| Constraint | Rule |
|---|---|
| **Blob storage** | Large files (CSV and derived artifacts) live in **S3** (presigned multipart/chunked upload). Postgres holds metadata and transactional SoR only. |
| **No whole-file RAM** | Never load a full 5–20 GB CSV into process memory. Use **streaming/chunked** reads (see `backend/app/api/chunked_upload.py`, `backend/tests/test_chunked_upload.py`). |
| **Request-scoped memory only** | Hold at most one active chunk/partition in memory per request. No unbounded module-level DataFrame caches across requests. |
| **Cross-worker / cross-pod** | FastAPI **Gunicorn workers** and **EKS replicas** must not assume sticky in-memory state for job status or datasets. Use **Redis** (session, rate limit, locks) and **S3** (e.g. `background_jobs.py` job snapshots under `midas_bg_jobs/`). |
| **Bounded caches** | Any in-process cache must have explicit **max entries + TTL/eviction**. Document estimated **bytes per entry × workers × replicas** when proposing caching. |
| **Multi-tenant scale** | Design for **~5 concurrent heavy users** (pods) scaling to **~20** without structural rewrites — prefer horizontal pod scaling + shared stores over per-user pod affinity. |
| **Helm awareness** | Backend chart (`deploy/ecs-app/helm/midas-api-backend-svc/`) sets `replicaCount`, `webConcurrency`, and high memory **requests**; raising replicas or workers multiplies RAM. Check node headroom before bumping counts. |
| **Done definition (scenario 4)** | Large-data/EKS changes are not complete without **automated test evidence** (chunked upload, perf ceiling tests) and **operational verification** notes (pod memory, worker count, S3/Redis behavior under concurrent users). |
| **Concurrency proposals** | When adding semaphores, thread pools, or caches, state **per-pod RAM** and **per-worker RAM** impact explicitly in the PR or architecture companion. |

Existing patterns to extend (do not bypass): chunked upload API, S3-backed background job status, `VirtualizedTable` / `react-window` on the frontend for large row displays.

---

## Technology Stack & Versions

### Backend

| Package | Version | Notes |
|---|---|---|
| Python | 3.13.x (pinned — `backend/Dockerfile`) | Match Dockerfile and local venv to 3.13 |
| FastAPI | latest (≥ 0.111) | No pinned version in requirements.txt — treat as ≥ 0.111 |
| Uvicorn + Gunicorn | latest | Production server |
| Pydantic | v2 (latest) | **Critical**: use v2 API — `model_dump()` not `.dict()`, `field_validator` not `validator`, `ConfigDict` not `class Config` |
| LiteLLM | **1.83.0** (pinned) | Multi-provider LLM routing — do not call provider SDKs directly |
| LangChain + LangGraph + langchain-core | latest (unpinned) | Agentic orchestration — API surface changes frequently; check existing patterns before adding new chains |
| SQLAlchemy | ≥ 2.0 + psycopg2-binary ≥ 2.9.9 | **Sync only** — `create_engine` / `Session`, not `AsyncSession`. Schema managed via `ensure_initialized()` on model classes (not Alembic) |
| Redis | ≥ 5.0 (redis-py client) | **Sync client** — matches synchronous SQLAlchemy pattern; session store + rate limiting |
| boto3 / botocore | ≥ 1.34 | AWS SDK — IRSA/instance profile for auth in pods, never long-lived access keys |
| scikit-learn | **1.6.0** (pinned) | ML training |
| XGBoost, LightGBM, CatBoost | latest | ML training — CatBoost causes sklearn deprecation warnings (suppressed in `main.py`) |
| SHAP | ≥ 0.42.0 | Model explainability |
| OpenTelemetry SDK | ≥ 1.24 | Metrics pushed to CloudWatch via boto3 PutMetricData |
| prometheus-client | ≥ 0.20 | FastAPI instrumentation via `prometheus-fastapi-instrumentator ≥ 7.0` |
| bcrypt | **3.2.2** (pinned) + passlib[bcrypt] | Password hashing |
| python-jose[cryptography] | latest | JWT — **legacy auth only**, do not use for new endpoints |
| litellm | **1.83.0** (pinned) | Already listed above — `litellm.drop_params = True` is set globally |
| pandas, polars, pyarrow, numpy, scipy, statsmodels | latest | Data processing |
| websockets | latest | Used for GraphRAG service communication; FastAPI WebSocket routes use FastAPI's native WebSocket support |

### LLM Routing (LiteLLM)

Three independent configs in `backend/app/core/config.py` and resolved in `backend/app/services/llm_service.py`:

| Usage type | Config object | Default model | Env prefix |
|---|---|---|---|
| Chat / general LLM | `CHAT_LLM_CONFIG` | `gpt-5.4-nano` | `LLM_CHAT_*` or `LLM_*` |
| Knowledge Graph | `KG_LLM_CONFIG` | `gpt-4.1-mini` | `LLM_KG_*` or `KG_*` |
| Embeddings | `EMBEDDING_LLM_CONFIG` | `text-embedding-3-small` | `LLM_EMBEDDING_*` or `EMBEDDING_*` |

- **AI Gateway toggle**: set `LLM_USE_GATEWAY=true` + `LLM_GATEWAY_URL` + `LLM_GATEWAY_VIRTUAL_KEY` to route all calls through the Exlerate AI Gateway (OpenAI-compatible endpoint). When enabled, provider-specific creds (Azure, Bedrock) are bypassed.
- **Never call Azure SDK, Bedrock boto3, or OpenAI SDK directly** — always go through LiteLLM via `llm_service.py`.
- Route to the right config object (`chat`, `knowledge_graph`, or `embedding`) — do not mix them.

### Frontend

| Package | Version | Notes |
|---|---|---|
| Node.js | ≥ 18.0.0 | |
| React | **18.3.1** | |
| TypeScript | **5.5.3** | `strict: true`, `noUnusedLocals`, `noUnusedParameters`, `noFallthroughCasesInSwitch`. No `any` without explicit `// eslint-disable-next-line` comment. All props must be typed. |
| Vite | **5.4.2** | ESNext modules, ES2020 target. Dev proxy: `/api` and `/health` → `:8000` |
| React Router DOM | **7.7.0** | |
| TailwindCSS | **3.4.1** | |
| Axios | **1.15.0** | HTTP client — all API calls via `apiInterceptor.ts` wrapper |
| Socket.IO client | **4.8.1** | Real-time events from backend |
| Vitest | **3.2.4** + jsdom **27** | Testing — test files: `src/**/*.test.ts` and `src/**/*.test.tsx` |
| Chart.js | **4.5.0** | Charting |
| Recharts | **3.2.1** | Charting |
| ExcelJS | **4.4.0** | Excel export |
| jsPDF | **4.2.1** | PDF export |
| html2canvas | **1.4.1** | Screenshot/canvas export — bundled into `vendor` chunk with xlsx |
| react-window | **2.2.7** | Virtualized lists — use for any list > ~100 rows |
| react-markdown + remark-gfm | latest | Markdown rendering |

### Infrastructure

| Service | Role | Constraint |
|---|---|---|
| AWS Region | `us-east-1` | **Only region — no cross-region** |
| VPC | `vpc-0c4d673f3e95a93eb` (CIDR `10.72.134.0/23`) | All workloads. No IGW, no NAT Gateway, no public IPs |
| Transit Gateway | `tgw-0ec391fa73943d562` | Only egress path for the VPC |
| EKS | Compute substrate | Workloads run on Kubernetes. Deploy via Helm. Images to ECR via Jenkins pipeline |
| AWS RDS PostgreSQL | Application persistence | DB name `exldecision-ai-modellab`. Schema via `ensure_initialized()` — never raw DDL or `create_all()` in new code |
| AWS ElastiCache (Redis) | Session store + rate limiting | Credentials from Secrets Manager (`SESSION_ELASTICACHE_SECRET_ARN`) |
| AWS S3 | Dataset / file object storage | Bucket access via presigned URLs. Key prefix controlled by `S3_UPLOAD_KEY_PREFIX` |
| AWS Cognito | **Primary auth** | Hosted UI + Entra ID federation. Refresh tokens in HttpOnly cookies |
| AWS Bedrock | LLM inference | Via PrivateLink. Accessed through LiteLLM only — not boto3 bedrock client directly |
| AWS Secrets Manager | All credentials | Read at runtime via boto3. Never in build-time env vars or Helm values |
| Jenkins | CI/CD | Pipeline-first — never run `helm upgrade` or `terraform apply` from laptop against shared envs |
| `ai_gateway/` submodule | Exlerate AI Gateway | **Read-only external submodule** — never edit any file under this directory |

---

## Critical Implementation Rules

### Language-Specific Rules — Python

**Logging (mandatory)**
- Always: `from app.core.logging_config import get_logger; log = get_logger(__name__)`
- Never: `import logging; logging.getLogger(...)` — bypasses handlers and JSON formatter
- Never: `print()` for diagnostics
- Every `log.*()` call beyond simple startup messages must include `extra={"event": "..."}` — required for CloudWatch Insights filters
- Exceptions must use `exc_info=True`: `log.error("msg", exc_info=True, extra={"event": "..."})`
- Do NOT add `from __future__ import annotations` — Pydantic v2 runtime validation breaks with postponed annotations in validators

**Error handling**
- Always re-raise with cause: `raise DomainError("msg") from exc` — never swallow, never bare `except:`
- Custom exceptions are domain-specific (e.g. `DataQualityError`, `DetectionError` in `app/services/data_quality_detector.py`) — follow the same pattern for new domains
- `StateConflictError` in `app/models/database.py` is the global 409 exception — the middleware in `main.py` converts it to HTTP 409 automatically; never return `{"error": ...}` for conflicts manually

**Types and Pydantic**
- Type hints on every function parameter and return value, including `-> None`
- Use `Optional[T]` (not `T | None`) in public signatures — project convention
- `from typing import Optional` — explicit import required
- Pydantic v2 for all boundary data: request/response bodies, config DTOs, external API shapes
  - `model_dump()` not `.dict()` — `field_validator` not `validator` — `ConfigDict` not `class Config`
  - `extra="forbid"` for config and response models
  - `extra="ignore"` + `ConfigDict(populate_by_name=True)` for request bodies with optional fields
  - Do NOT apply `frozen=True` to request models (breaks partial updates)
- Internal value objects (no I/O, no validation) use `@dataclass(frozen=True)`

**Structure and imports**
- Absolute imports only — no `from .foo import bar`
- All configuration read via `app.core.config.settings` — never `os.environ[...]` or `os.getenv(...)` outside `app/core/config.py`
- `pathlib.Path` over `os.path`
- PEP 8 naming: `snake_case` functions/variables, `PascalCase` classes, `UPPER_CASE` constants
- All route schemas live in `app/models/schemas.py` — add new Pydantic models there, not in route files

**Async discipline (FastAPI)**
- All FastAPI route handlers are `async def`
- Blocking I/O (synchronous SQLAlchemy calls, file reads, CPU-heavy transforms) must be wrapped: `await asyncio.get_event_loop().run_in_executor(None, blocking_fn, *args)` — never called directly inside `async def` bodies
- The project uses the **synchronous** SQLAlchemy driver (`create_engine`, `Session`) — do not introduce `AsyncSession` without a deliberate migration
- Auth is injected via `Depends(get_current_user_dependency)` from `app.api.auth_routes` — never extract tokens manually in route bodies

**HTTP error envelope (FastAPI standard)**
- Errors return: `{"detail": "<message>"}` (FastAPI default for `HTTPException`)
- Validation errors return: `{"detail": [{"loc": [...], "msg": "...", "type": "..."}]}`
- 409 conflicts return: `{"detail": "...", "error_type": "state_conflict", "dataset_id": ..., "expected_version": ..., "actual_version": ...}`
- Never invent custom top-level error keys — the frontend `apiInterceptor.ts` normalizes `detail` specifically

---

### Language-Specific Rules — TypeScript / React

**Type safety**
- `strict: true` enforced — no `any` without `// eslint-disable-next-line @typescript-eslint/no-explicit-any`
- All React component props typed with an interface or type alias — never untyped props
- Use `import type` for imports used only as TypeScript annotations (never in runtime code)
- No `.js` extensions in imports — Vite bundler mode resolves them

**API calls**
- All API calls go through `src/services/apiInterceptor.ts` (`apiInterceptor.get/post/put/delete`) — never use raw `fetch` or Axios directly
- `apiInterceptor.ts` uses native `fetch` internally (not Axios) and automatically injects `Authorization: Bearer <token>` + `X-Session-Id` via `buildMidasAuthHeaders()`
- Base URL: `resolveApiV1Base()` in `apiInterceptor.ts` reads `VITE_BASE_URL` env var and resolves to `/api/v1` — never hardcode the base URL
- Special error types thrown by interceptor: `SessionExpiredError`, `SilentAuthFailure`, `StateConflictError` — catch these by type in callers, never by message string
- 409 conflicts auto-dispatch `midas:state-conflict` window event — the `StateConflictModal` handles display; do not build local conflict UI

**Environment variables**
- All env vars: `import.meta.env.VITE_*` — never `process.env`
- Non-`VITE_`-prefixed vars are invisible to the bundle at runtime

**State management**
- Global state: React Context (`src/contexts/`) — no Redux, no Zustand, no React Query (not in project)
- Server state (API data, loading, error): `useState` + direct service calls inside components or contexts
- Never duplicate server state across multiple `useState` hooks in sibling components — lift to the appropriate Context

**React patterns**
- `useEffect` dependencies must be primitives or stable refs (`useCallback`, `useMemo`) — never plain object/array literals as deps (causes infinite re-renders; ESLint `react-hooks/exhaustive-deps` is enforced)
- Heavy pages (`ModelBuilder`, `ModelEvaluationMEEA`, `ModelComparisonDashboard`) are lazy-loaded via `React.lazy()` — apply the same pattern for any new heavy page
- Use `VirtualizedTable` (`src/components/VirtualizedTable.tsx`, backed by `react-window`) for any list > ~100 rows — never render large arrays directly
- No `console.log` in production code — ESLint `no-console` is set to `error`

**Chart libraries**
- Chart.js (`react-chartjs-2`) and Recharts are both present — check existing components in the same feature area before choosing; do not mix both in a single feature
- EXL brand chart colours: `src/constants/exlBrandChartColors.ts` — use these for all new charts

---

---

### Framework-Specific Rules — FastAPI

**Router and route structure**
- One `APIRouter` per domain in `app/api/` — add new routes to the matching file, or create a new router + register in `main.py`
- All routers mounted under `/api/v1` — never add at `/api/v2` or bare `/` without an ADR
- Every route decorator **must** declare `response_model=<SchemaClass>` — without it FastAPI serialises the full return object and leaks internal fields. All schemas live in `app/models/schemas.py`
- POST routes that create a resource must declare `status_code=status.HTTP_201_CREATED` — omitting it returns 200, which breaks REST clients
- Every router registered in `main.py` must include `tags=[...]` for OpenAPI grouping — match the pattern of existing routers

**Auth and session**
- Protected routes inject auth via `Depends(get_current_user_dependency)` from `app/api/auth_routes.py` — never extract tokens manually in route bodies
- `SessionValidationMiddleware` runs before route handlers and injects `request.state.session_user` for any validated Bearer token — read this attribute in routes that need the user object instead of calling auth logic again
- Public paths (no auth required) are registered via `IPublicPathPolicy` in `app/core/session/path_policy.py` — never patch `SessionValidationMiddleware` directly to add exemptions
- SSE streaming paths (`/api/v1/rfe/stream/*`, `/api/v1/auto-training/stream/*`) are explicitly skipped by both the middleware and the request-id middleware — any new streaming endpoint must be added to the same skip-lists in `main.py` and `session_validation.py`

**Database access**
- No `Depends(get_db)` pattern — DB access is through module-level service singletons: `message_state_db` (`app/models/database.py`), `model_evaluation_db`, `user_db`, `project_db`
- These singletons use a shared SQLAlchemy `create_engine` — sessions are opened and closed within each service method, never held across calls
- Schema is managed by `ensure_initialized()` called at startup in `main.py` — never call `Base.metadata.create_all()` directly in new code

**Background work and async**
- Sub-second fire-and-forget: `BackgroundTasks` (FastAPI built-in)
- Heavier background work: `app.state.executor` (`ThreadPoolExecutor`) — already attached at startup
- Never `asyncio.create_task()` for work that must survive the request lifetime — it is tied to the request's event loop iteration
- Blocking I/O inside an `async def` route: wrap with `await asyncio.get_event_loop().run_in_executor(None, fn, *args)`

**Middleware stack (outermost → innermost on ingress)**
```
RateLimitMiddleware → SessionValidationMiddleware → CORSMiddleware
  → request_id_middleware → log_requests → route handler
```
- New middleware must be added **after** `SessionValidationMiddleware` and before `RateLimitMiddleware` unless you have a specific reason — order is reversed from registration order in `main.py` (`add_middleware` appends to the front)
- `/health` and `/` are logged at `DEBUG` level (not `INFO`) — match this in any new health-adjacent path

---

### Framework-Specific Rules — React Frontend

**App structure**
- Context provider order in `App.tsx` is load-order dependent — **preserve it exactly**:
  `ThemeProvider` → `UserProvider` → `SessionExpiredModal` + `StateConflictModal` → `ReportsProvider` → `ChatsProvider` → `DocumentationProvider` → `DataProvider` + `DatabaseProvider`
- `useUser()` from `UserContext` is the auth gate — `isAuthenticated` controls the authenticated vs unauthenticated route tree; never duplicate this check
- `ProtectedRoute` (`src/components/ProtectedRoute.tsx`) must wrap every route in the authenticated tree — no exceptions
- `/auth/callback` must remain **outside** `ProtectedRoute` — it handles the Cognito redirect before auth state is known
- All new pages: add route to `App.tsx` **and** navigation entry to `Sidebar.tsx` — both must be updated together
- Heavy pages (`ModelBuilder`, `ModelEvaluationMEEA`, `ModelComparisonDashboard`) use `React.lazy()` with `<Suspense fallback={<RouteLoadingFallback />}>` — apply the same pattern to any new heavy page; the fallback component is already defined in `App.tsx`

**Dark mode / theming (non-negotiable)**
- Never hardcode `bg-white`, `text-black`, or `bg-gray-900` — use paired Tailwind light/dark classes as established in existing components (e.g. `bg-slate-50 dark:bg-gray-950`, `text-slate-600 dark:text-slate-300`)
- All `dark:` variants must be co-located with their light counterpart on the **same element** — never scatter theme overrides across child components
- Components rendered in portals (modals, tooltips, dropdowns) must explicitly consume `ThemeContext` — they escape the DOM tree and will not inherit `dark` class automatically
- `ThemeContext` is provided by `ThemeProvider` at the root — use `useTheme()` to read current theme

**Loading / empty / error states — all three required on every data-fetching page**
- **Loading**: use the established spinner/skeleton pattern — do not invent a new one per page
- **Empty**: zero-results state with a CTA — never return `null` or empty `<div>` during load (causes layout shift)
- **Error**: inline error with a retry action — `apiInterceptor.ts` throws typed errors; catch and display them

**Layout constraints**
- Main content sits inside `midas-app-main-scroll` — never set `overflow-hidden` on a page root without explicitly owning the scroll region
- Account for both sidebar states — collapsed (`lg:ml-16`) and expanded (`lg:ml-64`) are already applied on `<main>` in `AppContent`; page content must not assume a fixed left margin
- Minimum supported viewport: **1024px** with sidebar expanded

**Component rules**
- Page components (`src/pages/`) are thin orchestrators — wire context, handle routing state, compose feature components; do not put business logic or data fetching directly in JSX return blocks
- Shared UI primitives live in `src/components/` — never reimplement `Button`, `Badge`, `CollapsibleSection`, etc. inline on a new page
- EXL brand chart colours: `src/constants/exlBrandChartColors.ts` — use for all new charts; do not invent a local colour palette
- Typography: Tailwind type scale only — no inline `style={{ fontSize: '...' }}`; match heading hierarchy of existing pages (`text-2xl font-semibold` for page titles, `text-sm text-muted-foreground` for labels)

---

---

### Testing Rules — Backend (pytest)

**Structure**
- All test files live flat in `backend/tests/` — name `test_<module_or_feature>.py`
- Shared fixtures and utilities in `tests/conftest.py`
- Fixture DataFrames/datasets: `tests/fixtures/` as `.parquet` or `.csv` — never construct large DataFrames inline (they drift when schema changes)
- ML artifact I/O in tests: use `tmp_path` (pytest built-in) — never write to repo root or `/tmp` directly

**FastAPI route tests**
- Sync route tests: `from fastapi.testclient import TestClient` — `with TestClient(app) as tc: ...`
- Async concurrency tests (verify the event loop is not blocked): `from httpx import ASGITransport, AsyncClient` — `async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac: ...`
- **Always** set `monkeypatch.setenv("RATE_LIMIT_ENABLED", "false")` before creating `TestClient` — rate limiting will reject test requests otherwise
- **Auth bypass**: `app.dependency_overrides[get_current_user_dependency] = lambda: {"sub": "test-user"}` — never hit real auth in unit/integration tests. **Reset after every test** (use an `autouse` fixture): `yield; app.dependency_overrides.clear()`
- Every protected route **must** have a test asserting `401` when no `Authorization` header is present — auth enforcement tests are mandatory on financial analytics routes

**Test boundaries**

| Boundary | What to test | What to mock |
|---|---|---|
| Unit | Functions in `app/services/`, `app/utils/`, `app/core/` | DB singleton methods (`MagicMock`), S3/AWS (`moto`), HTTP (`respx`/`responses`) |
| Route/integration | FastAPI route → service layer | Auth (`dependency_overrides`), external I/O (`moto`/`respx`) |
| Never | Real boto3 without `moto`; `time.sleep()` for async side-effects; log output as primary assertion | — |

**Async tests**
- Async tests use `@pytest.mark.asyncio` + `AsyncMock` for mocked coroutines — never `asyncio.run()` inside a test body
- For performance/concurrency tests, use `asyncio.gather()` to verify event loop is not blocked (see `test_partition_preview_perf.py` for the pattern)

**ML service tests**
- Test the **contract** (shape, dtypes, column names, row count) — not model accuracy or learned weights
- Patch heavy training: `@patch.object(XGBClassifier, "fit", return_value=None)` — never train a real model in a unit test
- Performance ceiling tests: `assert dt < 5.0, f"took {dt:.2f}s"` — use `time.perf_counter()` and set realistic ceilings with CI headroom

**Pydantic v2 schema tests**
- Test invalid payloads with `pytest.raises(ValidationError)` — use `exc.value.error_count()` (v2 API), not `len(exc.value.errors())`
- Schema validation is a test surface — every new Pydantic model in `app/models/schemas.py` needs at least one invalid-payload test

**LLM / AI output tests**
- Services that return LLM-generated JSON must validate response structure with `jsonschema` before returning to the client
- Test stubs for LiteLLM: mock `litellm.acompletion` / `litellm.completion` — never call real providers in unit tests (cost + latency)

---

### Testing Rules — Frontend (Vitest)

**Structure**
- Test files co-located with the code they test: `src/components/Foo.tsx` → `src/components/Foo.test.tsx`
- Glob: `src/**/*.test.ts` and `src/**/*.test.tsx` (configured in `vite.config.ts`)
- Test environment: `jsdom` — browser globals (`window`, `document`, `localStorage`) available without import
- CI command: `npm run test` → `vitest run` (single pass, no watch)

**Mocking `apiInterceptor`**
- **Module mock** (unit tests — response shape doesn't affect logic under test):
  ```ts
  vi.mock('../services/apiInterceptor', () => ({
    apiInterceptor: { get: vi.fn(), post: vi.fn(), put: vi.fn(), delete: vi.fn() }
  }))
  // In afterEach:
  vi.clearAllMocks()
  ```
- **MSW** (optional, for integration tests where response shape drives component logic) — not currently installed; add `msw` to devDependencies if needed and use v2 API (`http.post(...)`, `HttpResponse.json(...)`)
- **Never** `global.fetch = vi.fn(...)` — patches after jsdom wires its fetch; behaviour is environment-order-dependent

**Required states for every data-fetching component**
Every component that fetches data must have tests for all three states:
1. **Loading** — spinner/skeleton visible before data arrives
2. **Empty** — zero-results state with CTA rendered
3. **Error** — error UI rendered when `apiInterceptor` rejects or returns non-2xx

**Auth and context**
- Wrap components in required Context providers in tests — a component using `useUser()` will throw if `UserProvider` is absent from the test tree
- `StateConflictError` and `SessionExpiredError` are thrown by `apiInterceptor` — test that components handle them (do not assume all errors are plain `Error`)

**Cross-user data isolation**
- Integration tests for data-fetching routes must assert that a valid token for User B cannot retrieve User A's session-scoped data — this is a mandatory test for any endpoint that scopes data by session or user ID

---

---

### Code Quality & Style — Python

**File organisation — most critical rule**
- `app/services/llm_service.py` is 3823 lines and `app/api/routes.py` is enormous — **do not append new capabilities to either of these files**
- Rule: any file already over 500 lines → **extract before you append** — create a new file for the new capability first, then add a thin call to it from the existing file
- New files must be named after a single noun: `llm_routing.py`, `session_factory.py`, `model_explainability.py` — if you cannot name it after one noun, the scope is still too broad
- Every service file must open with a **module-level responsibility docstring**:
  ```python
  """
  Handles LLM routing and provider selection only.
  Do NOT add model training or data processing here — use app/services/model_training.py.
  """
  ```

**Where to put new backend code**
```
New route handler      → app/api/<domain>_routes.py
Business logic         → app/services/<domain>_service.py  (new file if existing > 500 lines)
Pydantic API schema    → app/models/schemas.py  (single source — never define inline in route files)
Config / settings      → app/core/config.py
Reusable utility       → app/utils/<name>.py
AWS / external client  → app/core/<service>_client.py
LLM prompt templates   → app/services/prompts/<feature>.py  (new convention — establish going forward)
```

**LLM prompt templates (security rule)**
- Prompt templates must be **named constants** in `app/services/prompts/` — never inline f-strings that concatenate raw user input directly into a prompt
- User input that goes into a prompt must go through a sanitiser utility first — prevents prompt injection

**Import discipline**
- No wildcard imports: `from app.models.schemas import *` is forbidden — always explicit
- `TYPE_CHECKING` guard for type-only imports to avoid circular imports at runtime:
  ```python
  from typing import TYPE_CHECKING
  if TYPE_CHECKING:
      from app.services.some_service import SomeType
  ```
- `app.core.config.settings` is the only legal config access — never `import config` from a sibling module or `os.getenv` outside `app/core/config.py`

**Linting and formatting**
- Black (line length 88) + isort (or `ruff --select I`) + ruff — run before every commit
- `ruff` rules `F401` (unused imports) and `F841` (unused variables) are enabled — violations fail CI
- Pre-commit hooks: `black`, `ruff`, `isort`, `detect-secrets` (no hardcoded credentials), `mypy --strict` (where adopted)
- `pip-audit` runs in CI — fail on high/critical CVEs; never `pip install` against shared envs from laptop

**Documentation**
- Google-style docstrings on every public class and method: `Args`, `Returns`, `Raises`
- Inline comments explain **why** (non-obvious constraint, trade-off) — never **what** the code does
- Good: `# lucide-react excluded — causes HMR failure when pre-bundled (vite.config.ts)`
- Noise: `# increment counter`, `# return the result` — delete these
- Pydantic `Field(description=...)` required on every field in request/response schemas — this is what populates the OpenAPI docs; agents that skip it produce undocumented APIs:
  ```python
  algorithm: str = Field(..., description="ML algorithm. One of: xgboost, lightgbm, catboost, logistic_regression")
  max_iterations: int = Field(100, ge=1, le=1000, description="Max training iterations (1–1000)")
  ```

---

### Code Quality & Style — TypeScript / React

**Where to put new frontend code**
```
Full page                     → src/pages/<PageName>.tsx  (+ route in App.tsx + nav in Sidebar.tsx)
Reusable UI component         → src/components/<ComponentName>.tsx
Feature-specific component    → co-locate with the page that owns it
Global state                  → src/contexts/<Domain>Context.tsx
Service / API call             → src/services/<domain>Service.ts  or  <domain>Api.ts
Constants / colours           → src/constants/<name>.ts
```

**File and component discipline**
- One component per file; file name matches the default export (PascalCase)
- Service/utility files: camelCase (`chatOrchestrator.ts`, `authHeaders.ts`)
- Soft ceiling: ~300 lines per component — split into sub-components if significantly over
- No barrel `index.ts` files — import directly from the source file, never from a folder index
- Context providers with complex state: split into `<Domain>Context.tsx` (state + provider) and a `use<Domain>` consumer hook — keeps consumers from importing the entire provider module

**Linting enforcement**
- `no-console: error` — no `console.log` in production code; `console.warn` in the interceptor is the established exception
- `react-hooks/exhaustive-deps: error` — do not disable this rule; fix the deps instead
- `noUnusedLocals` and `noUnusedParameters` in `tsconfig.app.json` — TypeScript build fails on violations; never disable
- `@ts-ignore` is forbidden — use `@ts-expect-error` with a comment explaining why instead

**Styling**
- Tailwind utility classes only — no inline `style={{...}}` except for truly dynamic/computed values (e.g. `style={{ width: `${percent}%` }}`)
- Dark mode: paired light/dark classes on the same element — `bg-white dark:bg-gray-900` — never split across parent/child
- No magic numbers — define named constants in `src/constants/`
- Typography from Tailwind type scale only — no inline `fontSize` or `lineHeight`

---

---

### Development Workflow Rules

**Deployment — pipeline-first (non-negotiable)**
- Jenkins is the **only** deploy path to shared environments (dev, uat, prod)
- Never run `terraform apply`, `helm upgrade`, `helm install`, or any AWS/Kubernetes mutation from a laptop against a shared env
- Safe locally (read-only): `terraform plan`, `terraform validate`, `helm template`, linting
- Trigger pipeline: `.cursor/tools/jenkins_tools.py trigger --param ENVIRONMENT=dev` — confirm target env with the user before triggering
- Pipeline files: `deploy/Jenkinsfile_Deploy_App` (app + infra), `deploy/Jenkinsfile_Build` (image build + ECR push) — never modify these unless a pipeline code change is the explicit task

**Terraform and Helm structure**
- Terraform: `deploy/ecs-app/` — per-env tfvars at `deploy/ecs-app/tfvars/dev.tfvars`, `uat.tfvars`, `prod.tfvars` — never create a new `*.tfvars` without adding it to the pipeline
- Helm charts: `deploy/ecs-app/helm/<service>/` — one chart per service (`midas-api-backend-svc`, `midas-web-frontend-svc`, `midas-graph-svc`)
- Per-env Helm overrides: `values-midas-dev.yaml` alongside base `values.yaml` — this is the pattern to follow for new env-specific overrides
- **Never** put plaintext secret values in any Helm values file — all secrets via `secretRef` pointing at Kubernetes secrets seeded from AWS Secrets Manager
- ECR image tags must be the **Git commit SHA** — never tag as `latest` in any shared env (untraceable, unrollbackable)

**Secrets workflow — three-layer rule (in order)**
1. **Runtime secrets** → AWS Secrets Manager → injected at pod start via IRSA/Kubernetes secret
2. **Env-specific config** → Helm values file (`values-midas-dev.yaml`, etc.)
3. **Local dev only** → `backend/.env` (already gitignored in `backend/.gitignore`) — for non-secret local overrides only

To add a new secret: (a) add to Secrets Manager in the target env → (b) wire in Helm `secretRef` → (c) read via `app.core.config.settings` in code — **in that order**. Never reverse.

**Git discipline**
- All changes via PR — never push directly to `main` or `develop`
- Conventional commits: `feat:`, `fix:`, `chore:`, `docs:`, `refactor:`, `test:` — one logical change per commit
- Before every commit: `git diff --cached` to inspect staged changes — no `.env*` files, no AWS account IDs/ARNs, no hardcoded secrets
- Before every push: `git submodule status` — no `+` prefix (dirty/modified submodule SHA) — a dirty `ai_gateway/` SHA in a commit causes the pipeline to fail

**Git absolute prohibitions**
- Never `git push --force` or `--force-with-lease` to `main` or `develop`
- Never `git commit --amend` on an already-pushed commit
- Never `git submodule deinit`, `git rm ai_gateway`, or any destructive submodule operation without explicit user approval
- Never modify files under `ai_gateway/` — read-only external submodule
- Never change `.gitmodules` tracked branch without explicit user approval
- Never `git rebase -i` on shared branches — feature branches only, before PR opens

**PR checklist — all required before merge**
- `pip-audit -r backend/requirements.txt` exits 0 (no known CVEs)
- `npm audit --audit-level=high` exits 0 (from `frontend/`)
- All tests pass: `pytest` (backend), `npm run test` (frontend)
- No `.env*` files staged
- No hardcoded credentials, AWS account IDs, or ARNs in diff
- Helm values diff reviewed — no plaintext secrets
- `ai_gateway/` submodule SHA unchanged (unless explicit bump PR)
- ADR filed if required (see below)
- Breaking API change → deprecation notice in PR description

**Local development setup**
- Backend: Python 3.13.x in `python3.13 -m venv .venv` (or `python3` if it resolves to 3.13) — never system Python on the wrong minor version; `pip install -r requirements.txt`; no `--user` flag
- Frontend: `npm ci` (not `npm install`) to reproduce lockfile exactly — enforces `package-lock.json`
- Never commit `node_modules/`, `__pycache__/`, `*.env`, model artifacts (`*.pkl`, `rfe_artifacts/`)
- No real AWS credentials in shell env during development — use SSO profile (`aws sso login --profile <name>`) or `aws-vault`

**ADR requirement (`docs/adr/NNNN-<short-title>.md`)**
Required before implementing any of the following:
- New AWS service type not already in the architecture
- Any public endpoint
- New data store or change to a data store's owning service
- Change to AI/ML model provider or inference pattern
- Cross-region resources or traffic
- Change to Kubernetes resource limits/requests above baseline
- New external network egress path
- Any change that contradicts the Miro architecture diagram

**Breaking changes and promotions**
- Any change to an existing API response shape is a **breaking change** — requires deprecation notice in PR description and a versioning plan
- Any DB schema change must have a documented rollback script reviewed in the PR
- Environment promotion (dev → uat → prod) requires: all smoke tests passing, no open P1/P2 bugs, PM sign-off for uat → prod

---

## Critical Anti-Patterns — Never Do These

### Python / FastAPI

**Sync I/O inside async route handlers**
- Never call `requests.get()`, blocking `boto3`, or any synchronous I/O directly inside an `async def` route. All such calls must be wrapped with `asyncio.to_thread()`. The server will silently stall under load.
- Correct: `result = await asyncio.to_thread(boto3_client.describe_cluster, ...)`

**Pydantic v2 method mismatch (v1 method calls silently return wrong results)**
- Never use `.dict()` — use `.model_dump()`
- Never use `.parse_obj()` — use `MyModel.model_validate()`
- Never use `validator` / `@root_validator` — use `@field_validator` / `@model_validator`
- Never use `__fields__` — use `model_fields`

**Wrong session pattern**
- Never inject `get_db` via `Depends()` into routes — the project does NOT use dependency-injected sessions. Use `get_db_session()` from `app.core.database_engine` directly inside service methods.
- Never call `db.commit()` multiple times across disconnected layers — one logical operation = one commit.

**BackgroundTasks for long-running work**
- FastAPI `BackgroundTasks` is a post-response hook — it runs in the same process and can exhaust workers. Never use it for LLM calls, heavy ML inference, or file uploads that may take > 2 s. Use SQS/SNS or a separate async worker.

**Secrets in code or images**
- Never hardcode credentials, API keys, connection strings, or AWS account IDs in source code, Helm values, Dockerfile ENV, or environment variable defaults.
- All secrets live in AWS Secrets Manager. Retrieve them through `app.core.config.Settings` which reads from the environment / Secrets Manager on startup.

**Docker image tag `latest`**
- Never use `:latest` in Helm values, Terraform task definitions, or Dockerfiles. Always use a pinned SHA or semver tag. `latest` silently rolls back images on pod restarts.

**Session state pinned to a pod**
- Never store user session data, LLM conversation history, or in-flight job state in a module-level dict, global variable, or container-local file. HPA spins up N pods; subsequent requests can hit any pod. All mutable session state must live in ElastiCache (Redis).

**Unbounded LiteLLM concurrency**
- Never issue unlimited concurrent LiteLLM calls in a loop without a semaphore or rate-limiter. Use `asyncio.Semaphore` to cap concurrency and respect model TPM/RPM limits configured in `config.py`.

**Appending to already-large files**
- `backend/app/services/llm_service.py` (3 800 + lines) and `backend/app/api/routes.py` are already too large. Never append new capability to them. Decompose into focused service modules / router modules. New feature = new file.

**Schema changes without a rollback script**
- Never merge a PR that modifies a SQLAlchemy model (adds/removes/renames columns or tables) without a documented rollback script in the PR description. `ensure_initialized()` runs on startup; a bad migration can take down the service.

---

### TypeScript / React

**Direct mutation of React Context state**
- Never mutate objects held inside a Context value directly (e.g. `user.name = "new"`). Always call the setter produced by `useState` or `useReducer`. Direct mutation bypasses React's re-render cycle.

**Missing cleanup in `useEffect`**
- Every `useEffect` that sets up subscriptions, timers, WebSocket listeners, or AbortControllers **must** return a cleanup function. Missing cleanup causes memory leaks that accumulate across route navigations.

**Skipping the `apiInterceptor` for auth-protected calls**
- Never call `fetch()` or `axios` directly for API calls. All HTTP calls go through `apiInterceptor.ts` which injects the Cognito JWT and handles 401 refreshes. Direct calls will silently fail or expose unauthenticated requests.

**Hard-coded API base URLs**
- Never hard-code `http://localhost:8000/api/v1/` or any environment-specific URL. Use `resolveApiV1Base()` from `apiInterceptor.ts`.

**`any` type escape hatch**
- TypeScript strict mode is enabled. Never use `any` to silence a type error. Use `unknown` with a type guard, a discriminated union, or a proper interface. `@ts-ignore` requires a justification comment on the same line.

**Rendering large lists without virtualisation**
- Never render unbounded arrays (file rows, model lists, audit logs) with `.map()` directly in JSX. Use `react-window` (already in deps) for any list that can exceed ~50 items.

---

## Financial Data Rules

These rules apply to every route, service, and component that touches uploaded datasets, model outputs, or user-attributed results.

**PII handling**
- Never log raw financial values, account identifiers, SSNs, or any field tagged as PII in the data schema. Before logging, mask with `mask_pii(value)` (or an equivalent helper). If no helper exists, log the field name + `"[REDACTED]"`.
- Never expose PII fields in error responses sent to the frontend. API error bodies must contain only `code`, `message`, and optionally `trace_id`.

**Data retention**
- Uploaded datasets must not be stored indefinitely. Tie S3 object lifecycle policies to the retention period configured in `Settings.DATA_RETENTION_DAYS`. If that setting is absent, default to 90 days — never default to no expiry.
- Derived artefacts (model outputs, scenario results) inherit the same retention as the source dataset.

**Audit trail**
- Every mutation of a financial dataset, model configuration, or scenario definition must emit a structured audit log event: `{"event": "audit", "action": "...", "user_id": "...", "resource": "...", "timestamp": "..."}`.
- Audit events must be written before the mutation is committed so that a failed commit does not silently lose the audit record.

**Encryption at rest**
- Never write financial data to unencrypted storage. All S3 buckets use SSE-S3 or SSE-KMS (enforced by bucket policy). All RDS columns storing PII must use column-level application encryption or rely on the RDS KMS-encrypted cluster — verify before adding a new table.

**Data-scoped authorisation**
- Every endpoint that returns or modifies financial data must validate that the requesting user's `organisation_id` (from `request.state`) matches the data record's `organisation_id`. Never return cross-tenant records. This check must happen in the service layer, not only the route.
- Bulk-export endpoints must include row-count caps to prevent accidental full-table extraction.

**No financial data in frontend state beyond session**
- Never persist raw financial rows in `localStorage`, `sessionStorage`, or any browser-persisted store. In-memory React state only. If the user refreshes, they re-fetch from the API.

---

## Usage Guidelines

**For AI Agents:**
- Read this file before implementing any code in this project
- Follow ALL rules exactly as documented — do not substitute similar-looking alternatives
- When a rule conflicts with a general best practice, this file takes precedence
- When in doubt, prefer the more restrictive option
- If you discover a pattern in the codebase that contradicts a rule here, stop and flag it to the user before proceeding
- Update this file when new patterns are established (with user approval)

**For Humans:**
- Keep this file lean and focused on agent needs — remove rules that become obvious over time
- Update when the technology stack changes (version upgrades, library additions/removals)
- Review quarterly for outdated rules
- When a new ADR is accepted that changes a pattern, update the relevant rule here in the same PR

---

_Last Updated: 2026-05-27 (scenario test gate for 1–3; readiness in `_bmad-output/bmad-readiness.md`)_
_Originally generated by: bmad-generate-project-context skill — see also `_bmad-output/How to use BMAD for each scenario.md`_

# MIDAS Backend — Future State Architecture

**Audience:** Software developers  
**Status:** Proposed  
**Date:** 2026-04-28  
**Scope:** `backend/` — transition from monolith to 100% microservice architecture on AWS EKS + Istio

> **Visual diagrams →** [`future-state-architecture-diagram.md`](./future-state-architecture-diagram.md)  
> Contains four Mermaid diagrams: (1) full system layer view, (2) per-service code components, (3) GBM training sequence, (4) data handoff types reference.

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Current State — What We Are Moving Away From](#2-current-state--what-we-are-moving-away-from)
3. [Future State Principles](#3-future-state-principles)
4. [Service Decomposition Map](#4-service-decomposition-map)
5. [Service Catalogue](#5-service-catalogue)
6. [Authentication & Authorisation Deep-Dive](#6-authentication--authorisation-deep-dive)
7. [Data Fabric Deep-Dive](#7-data-fabric-deep-dive)
8. [Computation Service Deep-Dive (Kubeflow)](#8-computation-service-deep-dive-kubeflow)
9. [ALB + WAF Ingress Layer](#9-alb--waf-ingress-layer)
10. [AI Agent Fabric Deep-Dive (AWS AgentCore)](#10-ai-agent-fabric-deep-dive-aws-agentcore)
11. [Data & Storage Strategy](#11-data--storage-strategy)
12. [Cross-Cutting Abstractions](#12-cross-cutting-abstractions)
13. [Infrastructure Topology (EKS + Istio)](#13-infrastructure-topology-eks--istio)
14. [Inter-Service Communication Patterns](#14-inter-service-communication-patterns)
15. [Cloud-Portability Abstraction Layer](#15-cloud-portability-abstraction-layer)
16. [Secret Management](#16-secret-management)
17. [Caching Strategy (ElastiCache Redis)](#17-caching-strategy-elasticache-redis)
18. [State Migration Guide](#18-state-migration-guide)
19. [Developer Workflow](#19-developer-workflow)
20. [End-to-End Transaction: GBM Model Training](#20-end-to-end-transaction-gbm-model-training)
21. [Requirements Validation](#21-requirements-validation)
22. [Architecture Diagrams](#22-architecture-diagrams)

---

## 1. Executive Summary

The current MIDAS backend is a **single FastAPI monolith** (`backend/main.py` + `backend/app/`). It hosts ~15 functional domains in one process, uses process-local in-memory singletons for critical analytical state (DataFrames, LLM model selection, background jobs), and mixes SQLite, Postgres, and local file system as storage backends.

The future state decomposes this into **14 independent microservices** running as Kubernetes Pods on **AWS EKS**, connected through an **Istio service mesh**. Every service is stateless at the Pod level. Durable state lives exclusively in managed stores: **DynamoDB**, **ElastiCache Redis**, **S3**, and **AWS S3 Files**. Secrets are managed by **AWS Secrets Manager** only. All AWS-specific storage is accessed through a **portability abstraction layer** so the application code can run on Azure AKS or GCP GKE by swapping a single provider implementation.

Authentication and authorisation are handled by **two dedicated services**: `identity-service` (owns the Cognito integration, token issuance, and session lifecycle) and `authz-service` (owns RBAC policy evaluation — who is allowed to do what).

Data management is handled by a dedicated **`data-fabric-service`** — the single owner of all dataset storage, lifecycle, and metadata across S3 Files and S3. All other services request data through this service; they never access storage buckets directly.

All ML computation, pipeline authoring, and model training are delegated to **`computation-service`**, which runs on **Kubeflow Pipelines** on EKS. It provides a catalogue of reusable pipeline components, a pipeline builder API, and manages pipeline runs end-to-end. It replaces the current `training-orchestrator` + `training-worker` thread-based model entirely.

The web application is accessed through a dedicated **AWS Application Load Balancer (ALB)** with an integrated **AWS WAF (Web Application Firewall)**. The ALB is the single ingress point for all browser traffic into the EKS cluster. The WAF sits in front of the ALB and protects the application boundary before any request reaches the Istio Ingress Gateway.

A new **`agent-platform-service`** provides an AI Agent Fabric built on **AWS Bedrock AgentCore**. It abstracts AgentCore's managed runtime, session isolation, long-term memory, and outbound tool authentication, while running agent workloads on the EKS cluster in dedicated `midas-agents` namespace pods. The platform exposes every MIDAS capability (data fabric, analytics, computation, LLM, GraphRAG, evaluation, project management) as **Agent Tools** through the MCP (Model Context Protocol) and REST/gRPC interfaces — so an AI agent can perform any action a human user can. Out-of-the-box agents ship with the platform; users and developers can also compose and register new agents. See §10 for the full deep-dive.

---

## 2. Current State — What We Are Moving Away From

### 2.1 Monolith Snapshot

```
backend/
├── main.py                          ← Single FastAPI app, 1 process, all routers
├── app/
│   ├── api/
│   │   ├── routes.py                ← ~15k+ lines: upload + chat + QC + training + streaming
│   │   ├── rfe_routes.py
│   │   ├── project_routes.py
│   │   ├── auth_routes.py
│   │   ├── cognito_routes.py
│   │   └── documentation_routes.py
│   ├── services/                    ← All domain logic in one package
│   ├── models/                      ← Raw SQL (psycopg2 / sqlite3) — no ORM
│   └── core/                        ← Config, sessions, rate limits, LLM routing
```

### 2.2 Critical Pain Points (Why We Decompose)

| Pain Point | Impact |
|---|---|
| **In-memory DataFrames** (`DataFrameStateManager` singleton) | Cannot scale horizontally — all replicas diverge |
| **In-memory session LLM selection** (`llm_selection.py` process dict) | Lost on pod restart; sticky sessions required |
| **`BackgroundJobManager` threads** | No distributed visibility, no retry, lost on pod death |
| **SQLite fallback** | Cannot share state across pods; data diverges |
| **`routes.py` monolith** | One file owns upload, chat, QC, training, auto-train, streaming |
| **No external job queue** | Long ML training blocks HTTP request threads |
| **GraphRAG subprocess duality** | Same feature has two implementations: subprocess + HTTP client |
| **JWT `SECRET_KEY` in code** | Secret leaks into image layers / git history |
| **FAISS on local disk** | Vector index is not shared; diverges across replicas |

### 2.3 Current Domain Map (Monolith Slice View)

```
┌─────────────────────────────────────────────────────────┐
│                   FastAPI Monolith                       │
│  Auth │ Projects │ Dataset Upload │ QC/DQS │ LLM Chat   │
│  Feature Eng │ Model Training │ RFE │ MEEA │ GraphRAG   │
│  Documentation Gen │ Segmentation │ Auto-Training        │
├─────────────────────────────────────────────────────────┤
│  Process Memory │ SQLite/Postgres │ S3/LocalFS │ Redis   │
└─────────────────────────────────────────────────────────┘
```

---

## 3. Future State Principles

1. **Stateless pods.** No pod holds durable state. A pod can die, be rescheduled, or be replicated with zero data loss.
2. **One service, one database table namespace.** Services do not share DynamoDB tables or Redis keyspaces directly — access goes through the owning service's API.
3. **Event-driven for long work.** Any operation taking >3 seconds uses SQS → worker pattern. HTTP endpoints return a job ID immediately.
4. **Cloud-portable abstractions.** Application code imports `storage.StoragePort`, `cache.CachePort`, `secrets.SecretsPort` — never `boto3` directly. AWS adapters are in a dedicated `infra/` package.
5. **Istio owns traffic policy.** mTLS between all services, retry/circuit-breaker in `VirtualService`/`DestinationRule` — no per-service retry logic in code.
6. **Secrets Manager, never env vars for secrets.** Pods receive a secret reference; the abstraction layer fetches and caches the value at startup.
7. **DynamoDB first; cache with Redis.** Relational patterns from Postgres/SQLite are modelled as DynamoDB single-table or per-entity tables; hot reads are cached in ElastiCache Redis with TTL.
8. **ML artefacts and datasets on S3 Files.** No binary blobs in DynamoDB. The data layer writes parquet/pickle/models to S3; metadata (keys, sizes, ETags) go to DynamoDB.
9. **Portability parity.** Azure equivalent: Blob Storage + Cosmos DB + Azure Cache for Redis. GCP equivalent: GCS + Firestore + Memorystore Redis. The abstraction interfaces are identical across clouds.
10. **gRPC inside the mesh; REST at the boundary.** Service-to-service calls within the EKS cluster use **gRPC** (HTTP/2, Protocol Buffers, strongly-typed contracts). All external-facing endpoints — consumed by browsers, the frontend, CLI tools, or third-party integrations — expose a **RESTful HTTP/1.1 JSON API** via the Istio Ingress Gateway. No service exposes both transports for the same operation.

---

## 4. Service Decomposition Map

### 4.1 Monolith Code → Microservice

Every cell of the left column is a file that exists today in the monolith. Every cell of the right column is the microservice it moves into.

```
CURRENT MONOLITH FILE / MODULE          FUTURE MICROSERVICE
──────────────────────────────────      ──────────────────────────────────────────
app/api/auth_routes.py              ──► identity-service
app/api/cognito_routes.py           ──► identity-service
app/services/auth_service.py        ──► identity-service
app/core/session/session_factory.py ──► identity-service
app/core/http_auth.py               ──► identity-service (shared via midas-common)
app/models/user_database.py         ──► identity-service

[no current equivalent]             ──► authz-service  (new — RBAC engine)

app/api/project_routes.py           ──► project-service
app/models/project_database.py      ──► project-service

app/api/routes.py  /upload, /datasets,
app/services/dataset_service.py     ──► data-fabric-service
app/services/dataframe_state_manager.py ► data-fabric-service
app/services/object_storage/        ──► data-fabric-service

app/api/routes.py  /qc, /dqs,
  /correlations, /vif, /bivariate   ──► analytics-service
app/services/dqs_service.py         ──► analytics-service
app/services/data_quality_detector.py ► analytics-service
app/services/variable_review_service.py► analytics-service

app/api/routes.py  /chat,
  /execute-code                      ──► llm-service
app/services/llm_service.py         ──► llm-service
app/core/llm_routing.py             ──► llm-service
app/core/llm_registry.py            ──► llm-service
app/core/llm_selection.py           ──► llm-service

app/api/routes.py  /agent            ──► agent-platform-service  ← NEW
app/services/agentic_system.py      ──► agent-platform-service   ← MOVED from llm-service
[no current equivalent]             ──► agent-platform-service
                                        (AgentCore runtime mgmt, tool registry,
                                         agent catalogue, session lifecycle,
                                         long-term memory, MIDAS tool adapters)

app/api/routes.py  /train, /auto-train,
  /segment-train, /segment-auto      ──► computation-service (Kubeflow facade)
app/api/rfe_routes.py               ──► computation-service
app/services/model_training.py      ──► computation-service / pipeline components
app/services/model_training_auto_training.py► pipeline component
app/services/model_training_segment_*.py    ► pipeline component
app/services/feature_engineering_service.py ► pipeline component
app/services/model_training_rfe/    ──► pipeline component
app/services/model_training_pruning.py      ► pipeline component
app/services/background_jobs.py     ──► DELETED (replaced by Kubeflow Workflows)

app/api/documentation_routes.py     ──► documentation-service
app/models/model_evaluation_database.py ─► evaluation-service
app/services/model_evaluation_service.py ──► evaluation-service
app/services/model_evaluation_from_json.py ► evaluation-service
app/services/graphrag_service.py    ──► graphrag-service
app/services/graphrag_client.py     ──► graphrag-service
app/services/graphrag_process_manager.py ──► DELETED (whole service IS the process)
app/services/vector_store.py        ──► graphrag-service (FAISS → OpenSearch)

app/models/database.py              ──► llm-service (midas-messages table)
app/models/schemas.py               ──► split per service (each owns its Pydantic models)
app/models/_db_backend.py           ──► DELETED (replaced by NoSQLPort → DynamoDB)
app/core/rate_limit_store.py        ──► midas-common middleware (shared)
app/core/executor.py                ──► DELETED (ThreadPoolExecutor not needed in pods)
```

---

### 4.2 Future Service Repository Structure

Each microservice is a **standalone Python package** in a monorepo layout. They share nothing except `midas-common`.

```
services/
├── identity-service/
│   ├── Dockerfile
│   ├── pyproject.toml
│   ├── main.py                    ← FastAPI app factory + gRPC server start
│   └── app/
│       ├── api/                   ← REST handlers (external boundary)
│       │   ├── login_routes.py    ← GET /api/v1/identity/login-url, /callback
│       │   ├── session_routes.py  ← POST /api/v1/identity/refresh, /logout, /me
│       │   └── jwks_routes.py     ← GET /api/v1/identity/jwks
│       ├── grpc/                  ← gRPC servicers (internal boundary)
│       │   └── identity_servicer.py  ← VerifyToken, GetUser RPCs
│       ├── services/
│       │   ├── cognito_service.py ← Cognito PKCE exchange logic
│       │   ├── session_service.py ← Redis session create/read/delete
│       │   └── user_service.py    ← DynamoDB user provisioning
│       └── models/
│           └── schemas.py         ← Pydantic request/response models
│
├── authz-service/
│   ├── Dockerfile
│   ├── pyproject.toml
│   ├── main.py
│   └── app/
│       ├── api/                   ← REST (role management admin endpoints only)
│       │   └── roles_routes.py
│       ├── grpc/
│       │   └── authz_servicer.py  ← CheckPermission, GetUserPermissions RPCs
│       ├── services/
│       │   ├── rbac_service.py    ← DynamoDB RBAC table lookups
│       │   └── cache_service.py   ← Redis permission cache
│       └── models/
│           └── schemas.py
│
├── data-fabric-service/
│   ├── Dockerfile
│   ├── pyproject.toml
│   ├── main.py
│   └── app/
│       ├── api/                   ← REST (upload, list, preview)
│       │   └── data_routes.py
│       ├── grpc/
│       │   └── data_fabric_servicer.py  ← GetDataframe, RegisterArtefact, etc.
│       ├── services/
│       │   ├── upload_service.py  ← S3 raw write + parquet conversion
│       │   ├── split_service.py   ← Train/test split logic
│       │   └── catalogue_service.py ← DynamoDB midas-data-catalogue CRUD
│       └── models/
│           └── schemas.py
│
├── computation-service/
│   ├── Dockerfile
│   ├── pyproject.toml
│   ├── main.py
│   └── app/
│       ├── api/
│       │   ├── pipeline_routes.py ← CRUD for pipelines + catalogue
│       │   ├── component_routes.py← CRUD for components
│       │   └── run_routes.py      ← Trigger runs, status, SSE stream
│       ├── grpc/
│       │   └── computation_servicer.py ← SubmitRun, GetRunStatus RPCs
│       ├── services/
│       │   ├── kubeflow_service.py← Kubeflow Pipelines SDK wrapper
│       │   ├── pipeline_service.py← DynamoDB pipeline-catalogue CRUD
│       │   └── run_service.py     ← DynamoDB pipeline-runs + SSE bridge
│       └── models/
│           └── schemas.py
│
├── pipeline-components/           ← Kubeflow pipeline step implementations
│   ├── feature_engineer/
│   │   ├── Dockerfile             ← Own image; Python 3.12; heavy ML deps
│   │   └── component.py           ← @kfp.component decorated function
│   ├── gbm_trainer/               ← GBM / LightGBM / CatBoost / XGBoost
│   │   ├── Dockerfile
│   │   └── component.py
│   ├── lr_trainer/                ← Logistic Regression
│   ├── rfe_selector/              ← Recursive Feature Elimination
│   ├── auto_trainer/              ← FLAML / TPOT auto-ML
│   └── meea_evaluator/            ← Model Evaluation + Error Analysis
│
├── analytics-service/
├── llm-service/
├── project-service/
├── documentation-service/
├── evaluation-service/
├── graphrag-service/
└── agent-platform-service/        ← NEW
    ├── Dockerfile
    ├── pyproject.toml
    ├── main.py                    ← FastAPI app + gRPC server
    └── app/
        ├── api/                   ← REST endpoints (external boundary)
        │   ├── agent_routes.py    ← CRUD agents, run agents, stream responses
        │   ├── tool_routes.py     ← list/register/delete platform tools
        │   └── memory_routes.py   ← read/delete agent long-term memory
        ├── grpc/
        │   └── agent_servicer.py  ← InvokeAgent, StreamAgent, GetAgentStatus RPCs
        ├── services/
        │   ├── agentcore_service.py   ← AgentCore SDK wrapper (Runtime CRUD, InvokeAgentRuntime)
        │   ├── tool_registry.py       ← MCP tool adapter factory; exposes MIDAS services as tools
        │   ├── memory_service.py      ← AgentCore Memory API wrapper (short-term + long-term)
        │   ├── session_service.py     ← AgentCore session lifecycle management
        │   └── agent_catalogue_service.py  ← DynamoDB midas-agent-catalogue CRUD
        ├── tools/                 ← MCP tool adapter implementations
        │   ├── data_fabric_tool.py    ← wraps DataFabricClient gRPC → MCP tool
        │   ├── analytics_tool.py      ← wraps AnalyticsClient gRPC → MCP tool
        │   ├── computation_tool.py    ← wraps ComputationClient gRPC → MCP tool
        │   ├── llm_tool.py            ← wraps LLMClient gRPC → MCP tool
        │   ├── graphrag_tool.py       ← wraps GraphRAGClient gRPC → MCP tool
        │   ├── evaluation_tool.py     ← wraps EvaluationClient gRPC → MCP tool
        │   ├── project_tool.py        ← wraps ProjectClient gRPC → MCP tool
        │   └── authz_tool.py          ← wraps AuthzClient gRPC → MCP tool (permission checks)
        └── models/
            └── schemas.py

midas-common/                      ← shared package (pip install midas-common)
├── midas/
│   ├── ports/                     ← StoragePort, CachePort, NoSQLPort, SecretsPort, QueuePort
│   ├── adapters/aws/              ← S3, DynamoDB, Redis, Secrets Manager adapters
│   ├── proto/                     ← .proto files + generated gRPC stubs for all services
│   ├── clients/                   ← Pre-built gRPC clients (AuthzClient, DataFabricClient, etc.)
│   ├── middleware/                ← Rate limiting, request ID, JWT extraction (shared)
│   └── factory.py                 ← get_storage(), get_cache(), get_nosql(), etc.
```

---

---

## 5. Service Catalogue

### 5.1 `identity-service`

**Current code:** `auth_routes.py`, `cognito_routes.py`, `auth_service.py`, `core/session/session_factory.py`, `core/http_auth.py`, `models/user_database.py`

**Responsibility:** The single source of truth for *who the user is*. Owns the Cognito integration, token issuance (ID token + access token), session lifecycle, and user provisioning. **Does not make permission decisions** — that is `authz-service`.

| Item | Detail |
|---|---|
| **External REST endpoints** | `GET /api/v1/identity/login-url`, `GET /api/v1/identity/callback` (PKCE exchange), `POST /api/v1/identity/refresh`, `POST /api/v1/identity/logout`, `GET /api/v1/identity/me`, `GET /api/v1/identity/jwks` |
| **Internal gRPC RPCs** | `VerifyToken(token) → UserContext`, `GetUser(user_id) → UserRecord` — consumed by other services over gRPC port 50051 |
| **Inbound consumers** | Istio `RequestAuthentication` validates JWTs at the mesh layer using `/api/v1/identity/jwks`. Other services call `VerifyToken` via gRPC — never the REST `/me` endpoint. |
| **Cognito integration** | Service exchanges the authorisation code for Cognito tokens, then issues a **short-lived MIDAS session token** (JWT, HS256, signed with key from Secrets Manager). The Cognito `access_token` is never forwarded to downstream services — only the MIDAS session JWT is. |
| **Session storage** | Active sessions → **ElastiCache Redis** (`session:{jti}` → serialised user context, TTL = token expiry). On `POST /v1/identity/logout` the Redis key is deleted immediately (token blacklisting). |
| **User records** | JIT-provisioned users → **DynamoDB** `midas-users` table (PK: `user_id`, attributes: email, Cognito `sub`, created_at). Refresh token hashes also stored here. |
| **Secrets** | `/midas/identity/cognito-client-id`, `/midas/identity/cognito-client-secret`, `/midas/identity/jwt-signing-key` — all via `SecretsPort.get()` |
| **Removed** | Legacy password login (`ENABLE_LEGACY_PASSWORD_LOGIN`), bcrypt/passlib, `SECRET_KEY = "your-secret-key"` placeholder, `auth_service.py` HS256 manual logic |
| **Portability** | `SecretsPort` for all key material. Cognito is AWS-specific — on Azure replace with **Azure AD B2C** or **Entra External ID** by swapping the OAuth exchange adapter only; session + user storage remain unchanged. |

---

### 5.2 `authz-service`

**Current code:** No dedicated equivalent exists today. Permission checks are implicit (route-level `Depends(get_current_user)`) with no formal RBAC model.

**Responsibility:** The single source of truth for *what the user is allowed to do*. Owns role assignments, permission definitions, and policy evaluation. All services that need to answer "can user X perform action Y on resource Z?" call this service — they do not implement their own permission logic.

**Why a separate service?**

- Roles and permissions evolve independently of identity (e.g. adding a new `data-steward` role does not touch login flows).
- Centralising RBAC means audit trails, policy changes, and compliance reviews happen in one place.
- Istio `AuthorizationPolicy` enforces coarse-grained service-to-service access; `authz-service` enforces fine-grained resource-level RBAC within the mesh.

| Item | Detail |
|---|---|
| **External REST endpoints** | `GET /api/v1/authz/roles`, `POST /api/v1/authz/roles`, `PUT /api/v1/authz/users/{user_id}/roles`, `DELETE /api/v1/authz/users/{user_id}/roles/{role}`, `GET /api/v1/authz/users/{user_id}/permissions` — admin / management operations only |
| **Internal gRPC RPCs** | `CheckPermission(user_id, action, resource_type, resource_id) → CheckPermissionResponse`, `GetUserPermissions(user_id) → PermissionList` — the hot path; never exposed externally |
| **Note** | `CheckPermission` is **gRPC-only, internal-only**. No REST equivalent exists by design. |
| **RBAC model** | Three-layer: **Roles** (named sets of permissions, e.g. `analyst`, `admin`, `viewer`), **Permissions** (action + resource-type pairs, e.g. `dataset:upload`, `model:train`, `project:delete`), **Assignments** (user → role → optional project/tenant scope) |
| **State** | Role definitions → **DynamoDB** `midas-roles` (PK: `role_id`). Permission definitions → **DynamoDB** `midas-permissions`. User-role assignments → **DynamoDB** `midas-user-roles` (PK: `user_id`, SK: `role_id#scope`). Hot permission checks → **ElastiCache Redis** (`authz:{user_id}:{resource_type}`, TTL 5 min) |
| **How other services use it** | Services call `POST /v1/authz/check` with `{user_id, action, resource_type, resource_id}`. Response: `{allowed: true/false, reason: "..."}`. This replaces scattered `if user.role == "admin"` checks. |
| **Istio integration** | Istio `AuthorizationPolicy` (service-to-service mTLS) + `authz-service` (user-to-resource RBAC) are **complementary, not overlapping**. Istio decides whether service A can talk to service B. `authz-service` decides whether user X can perform action Y. |
| **Cache invalidation** | On role assignment change → `authz-service` deletes affected Redis keys. TTL (5 min) is the max stale window if invalidation is missed. |
| **Secrets** | None beyond standard IRSA. DynamoDB access via `NoSQLPort`. |
| **Portability** | RBAC model is cloud-agnostic. On Azure, DynamoDB tables swap to Cosmos DB via `NoSQLPort`; Redis cache swaps to Azure Cache for Redis via `CachePort`. |

**Default RBAC roles (seed data):**

| Role | Permissions |
|---|---|
| `admin` | All permissions across all resources |
| `analyst` | `dataset:upload`, `dataset:read`, `model:train`, `model:read`, `project:read`, `project:create` |
| `viewer` | `dataset:read`, `model:read`, `project:read` |
| `data-steward` | `dataset:upload`, `dataset:read`, `dataset:delete`, `project:read` |

**Developer usage pattern:**

```python
# In any downstream service — inject the authz client from midas-common
from midas.clients.authz import AuthzClient

authz = AuthzClient(base_url="http://authz-service.midas-services.svc.cluster.local")

async def upload_dataset(user_id: str, project_id: str, file: bytes):
    check = await authz.check(
        user_id=user_id,
        action="dataset:upload",
        resource_type="project",
        resource_id=project_id,
    )
    if not check.allowed:
        raise PermissionDeniedError(check.reason)
    # ... proceed with upload
```

**Request flow through identity + authz:**

```
1. Client presents MIDAS session JWT in Authorization: Bearer <token>
2. Istio RequestAuthentication validates JWT signature (JWKS from identity-service)
3. Service handler extracts user_id from validated JWT claims
4. Service calls authz-service POST /v1/authz/check  {user_id, action, resource_id}
5. authz-service checks Redis cache → hit: return immediately
                                    → miss: DynamoDB lookup → cache + return
6. Service proceeds or returns 403
```

---

### 5.3 `project-service`

**Current code:** `project_routes.py`, `project_database.py`

**Responsibility:** CRUD for projects; the anchor entity that links users → datasets → training runs.

| Item | Detail |
|---|---|
| **External REST endpoints** | `GET/POST /api/v1/projects`, `GET/PUT/DELETE /api/v1/projects/{id}` |
| **Internal gRPC RPCs** | `GetProject(project_id)`, `ListProjectsForUser(user_id)` — consumed by `dataset-service`, `analytics-service` |
| **State** | **DynamoDB** `midas-projects` table. PK: `project_id`, GSI on `user_id` |
| **Current migration** | Raw SQL `projects` table → DynamoDB single-table model |

---

### 5.4 `data-fabric-service` _(new)_

**Current code:** `routes.py` (`/upload`, `/datasets`, `/split`), `dataset_service.py`, `dataframe_state_manager.py`, `services/object_storage/`

**Responsibility:** The single owner of all data in MIDAS. Every dataset, raw file, split configuration, and processed artefact is stored and retrieved through this service. No other service writes to or reads from S3/S3 Files directly — they call `data-fabric-service` over gRPC. This is a data-centric service that creates and manages the full data lifecycle. See §7 for the full deep-dive.

| Item | Detail |
|---|---|
| **External REST endpoints** | `POST /api/v1/data/upload`, `GET /api/v1/data/datasets`, `GET /api/v1/data/datasets/{id}`, `POST /api/v1/data/datasets/{id}/split`, `GET /api/v1/data/datasets/{id}/preview`, `GET /api/v1/data/datasets/{id}/versions`, `DELETE /api/v1/data/datasets/{id}` |
| **Internal gRPC RPCs** | `GetDataset(dataset_id) → DatasetMeta`, `GetDataframe(dataset_id, scope) → ParquetBytes`, `ListDatasets(project_id) → DatasetList`, `GetRawFile(dataset_id, filename) → FileBytes`, `RegisterArtefact(job_id, key, type) → ArtefactRef` |
| **Storage** | Raw uploads → **AWS S3** (`midas-raw/`). Processed parquet, splits → **AWS S3 Files** (`midas-datasets/parquet/`, `midas-datasets/splits/`). ML artefacts → **AWS S3 Files** (`midas-artefacts/`). Metadata → **DynamoDB** `midas-data-catalogue` |
| **Hot cache** | DataFrames cached in **ElastiCache Redis** (`df:{dataset_id}:{scope}`, LZ4 parquet bytes, TTL 30 min). Cache miss triggers S3 Files read. |
| **Data catalogue** | Every dataset, version, artefact, and split is registered in DynamoDB `midas-data-catalogue`. Supports lineage: `dataset → split → training-run → artefact`. |
| **Removed** | `DataFrameStateManager` process singleton, `split_configs_state.json`, direct `boto3.client('s3')` calls outside this service |

---

### 5.5 `analytics-service`

**Current code:** `routes.py` (`/qc`, `/dqs`, `/correlations`, `/vif`, `/bivariate`, `/column-insights`), `dqs_service.py`, `data_quality_detector.py`, `variable_review_service.py`

**Responsibility:** Stateless compute — receives a `dataset_id` + config, fetches the DataFrame from `data-fabric-service` (via gRPC + cache), runs statistical analysis, returns results.

| Item | Detail |
|---|---|
| **External REST endpoints** | `POST /api/v1/analytics/qc`, `POST /api/v1/analytics/dqs`, `POST /api/v1/analytics/correlations`, `POST /api/v1/analytics/vif`, `POST /api/v1/analytics/bivariate` |
| **Internal gRPC RPCs** | `RunQC(dataset_id, config) → job_id`, `GetResult(job_id) → AnalyticsResult` — consumed by `computation-service` to gate pipeline execution |
| **State** | None in Pod. Input data from `data-fabric-service`. Results stored in **DynamoDB** `midas-analytics-results` (keyed by `dataset_id + analysis_type + run_id`) |
| **Scaling** | CPU-bound — scale independently with `HorizontalPodAutoscaler` on CPU >60% |

---

### 5.6 `llm-service`

**Current code:** `routes.py` (chat/agent/execute-code), `llm_service.py`, `agentic_system.py`, `core/llm_routing.py`, `core/llm_registry.py`, `core/llm_selection.py`

**Responsibility:** Chat, agentic reasoning, execute-code, LLM model routing/registry. Thin proxy to the AI Gateway; owns conversation history persistence.

| Item | Detail |
|---|---|
| **External REST endpoints** | `POST /api/v1/chat/completions`, `POST /api/v1/chat/agent`, `POST /api/v1/chat/execute-code`, `GET /api/v1/chat/models` |
| **Internal gRPC RPCs** | `Chat(session_id, messages) → stream ChatChunk` — consumed by `documentation-service` for LLM-assisted doc generation |
| **LLM backend** | Calls **AI Gateway** (LiteLLM proxy) via OpenAI-compatible REST API inside VPC PrivateLink — the AI Gateway is an external dependency, not a MIDAS service, so REST is correct here |
| **State** | Conversation history → **DynamoDB** `midas-messages` (replaces Postgres `message_states`). Model selection overrides → **ElastiCache Redis** (`llm-select:<session_id>`, TTL = session TTL). No in-memory dicts. |
| **Removed** | `_session_selections` process dict in `llm_selection.py` → Redis |
| **Streaming** | SSE responses proxied through Istio. SSE pods scale independently |

---

### 5.7 `computation-service` _(new — replaces training-orchestrator + training-worker)_

**Current code:** `routes.py` (train/auto-train/segment-train/segment-auto-train), `background_jobs.py`, `model_training*.py`, `feature_engineering_service.py`, `model_training_rfe/`, `model_training_pruning.py`, `rfe_routes.py`

**Responsibility:** All ML computation, pipeline authoring, pipeline management, and execution. Built on **Kubeflow Pipelines** running on EKS. Provides a REST+gRPC API for creating pipeline components, building pipelines from components, triggering runs, and browsing a pipeline and component catalogue. See §8 for the full deep-dive.

| Item | Detail |
|---|---|
| **External REST endpoints** | `POST /api/v1/computation/pipelines`, `GET /api/v1/computation/pipelines`, `GET /api/v1/computation/pipelines/{id}`, `PUT /api/v1/computation/pipelines/{id}`, `DELETE /api/v1/computation/pipelines/{id}`, `POST /api/v1/computation/pipelines/{id}/runs`, `GET /api/v1/computation/runs/{id}`, `GET /api/v1/computation/runs/{id}/stream` (SSE), `POST /api/v1/computation/runs/{id}/cancel`, `GET /api/v1/computation/components`, `POST /api/v1/computation/components`, `PUT /api/v1/computation/components/{id}`, `DELETE /api/v1/computation/components/{id}`, `GET /api/v1/computation/functions` |
| **Internal gRPC RPCs** | `SubmitRun(pipeline_id, params) → RunRef`, `GetRunStatus(run_id) → RunStatus` — consumed by `analytics-service` post-QC and by `evaluation-service` |
| **Kubeflow** | `computation-service` is the MIDAS API facade over **Kubeflow Pipelines SDK**. It translates MIDAS API calls to Kubeflow `PipelineRun` objects. Kubeflow schedules individual pipeline steps as **Argo Workflow** pods in the `midas-pipelines` namespace. |
| **Data input** | Pipeline components receive `dataset_id` — they call `data-fabric-service` over gRPC to fetch the DataFrame. They never receive raw files directly. |
| **Artefact output** | Trained models, evaluation files, feature importance outputs are registered back to `data-fabric-service` via `RegisterArtefact` gRPC. |
| **Catalogue** | Pipeline definitions, component specs, and function metadata stored in **DynamoDB** `midas-pipeline-catalogue`. |
| **Removed** | `BackgroundJobManager` threads, `training_jobs_state.json`, SQS-based job dispatch, in-process `ThreadPoolExecutor`, KEDA/SQS worker pattern |

---

### 5.8 `documentation-service`

**Current code:** `documentation_routes.py`, helpers in `services/`

**Responsibility:** LLM-driven documentation generation. Stateless — calls `llm-service` for LLM completion, builds docx/xlsx, stores output in S3.

| Item | Detail |
|---|---|
| **External REST endpoints** | `POST /api/v1/documentation/generate`, `GET /api/v1/documentation/{job_id}/status`, `GET /api/v1/documentation/{job_id}/download` |
| **Internal gRPC RPCs** | None — this service is a consumer, not a provider. It calls `llm-service` via gRPC for completions. |
| **State** | Generated doc files → **S3** `midas-documentation/`. Job state → **DynamoDB** `midas-doc-jobs` |
| **Pattern** | Async SQS job (generation can take minutes for large docs) |

---

### 5.9 `evaluation-service`

**Current code:** `model_evaluation_service.py`, `model_evaluation_database.py`, `model_evaluation_from_json.py`

**Responsibility:** Store, retrieve, and compute MEEA (Model Evaluation and Error Analysis) records.

| Item | Detail |
|---|---|
| **External REST endpoints** | `POST /api/v1/evaluation`, `GET /api/v1/evaluation/{model_id}`, `GET /api/v1/evaluation/{model_id}/compare` |
| **Internal gRPC RPCs** | `StoreEvaluation(model_id, payload) → EvalRef` — called by `training-worker` after a training run completes |
| **State** | MEEA rows → **DynamoDB** `midas-evaluations`. Compressed evaluation payloads → **S3** (referenced by DynamoDB item key). Replace the Postgres `model_evaluation_db` raw SQL pattern. |

---

### 5.10 `graphrag-service`

**Current code:** `graphrag_service.py`, `graphrag_process_manager.py`, `graphrag_client.py`, `vector_store.py`

**Responsibility:** Knowledge graph construction, querying, and vector search. Already partially isolated as an HTTP service on port 8001.

| Item | Detail |
|---|---|
| **External REST endpoints** | `POST /api/v1/graphrag/build`, `POST /api/v1/graphrag/query`, `GET /api/v1/graphrag/health`, `POST /api/v1/vector/search`, `POST /api/v1/vector/index` |
| **Internal gRPC RPCs** | `Query(dataset_id, query_text) → KGQueryResult`, `VectorSearch(embedding, top_k) → SearchResults` — consumed by `llm-service` for RAG context retrieval |
| **Deployment** | Dedicated Pod with Python 3.12 base image (current subprocess-spawns-Python-3.12 hack is eliminated). |
| **State** | Graph cache → **S3** `midas-knowledge-graphs/`. Vector index → **Amazon OpenSearch Serverless** (replaces FAISS on disk — shared, persistent, searchable). Metadata → **DynamoDB** `midas-graphrag-meta`. |
| **Removed** | `graphrag_process_manager` subprocess lifecycle (whole service is the process). `vector_store.py` FAISS files on local disk. |

---

### 5.11 `agent-platform-service` _(new)_

**Current code:** `routes.py` (`/agent`), `services/agentic_system.py` — both extracted from the monolith. All AgentCore-level capabilities are **new**.

**Responsibility:** The AI Agent Fabric for MIDAS. Provides a managed environment for defining, running, and interacting with AI agents built on **AWS Bedrock AgentCore**. It abstracts AgentCore's Runtime, session lifecycle, long-term memory, and outbound tool authentication from all consumers. It exposes every MIDAS platform capability (data fabric, analytics, computation, LLM, GraphRAG, evaluation, project management, auth/authz) as **Agent Tools** so agents can drive the full platform programmatically — just as a human user does through the web UI. See §10 for the full deep-dive.

**Agent types shipped out-of-the-box:**
- `data-qa-agent` — autonomously runs QC, DQS, and correlation analysis on a dataset
- `train-agent` — end-to-end model training: upload data → QC → feature engineering → train → evaluate
- `insight-agent` — combines LLM chat + GraphRAG + analytics to answer questions about a dataset
- `doc-agent` — generates full model documentation from a completed training run
- `pipeline-builder-agent` — helps a user compose and validate a custom Kubeflow pipeline

| Item | Detail |
|---|---|
| **External REST endpoints** | `GET /api/v1/agents` (list catalogue), `POST /api/v1/agents` (register new agent), `GET /api/v1/agents/{id}` (get definition), `PUT /api/v1/agents/{id}` (update), `DELETE /api/v1/agents/{id}`, `POST /api/v1/agents/{id}/runs` (invoke), `GET /api/v1/agents/runs/{run_id}` (status), `GET /api/v1/agents/runs/{run_id}/stream` (SSE / WebSocket), `GET /api/v1/agents/tools` (list platform tools), `DELETE /api/v1/agents/memory/{user_id}` (clear long-term memory) |
| **Internal gRPC RPCs** | `InvokeAgent(agent_id, session_id, input) → stream AgentChunk`, `GetAgentStatus(run_id) → AgentRunStatus`, `ListAgentTools() → ToolList` — consumed by `llm-service` when orchestrating multi-step agentic flows |
| **AgentCore integration** | `agentcore_service.py` wraps `boto3.client("bedrock-agentcore-runtime")`. Calls: `CreateAgentRuntime`, `InvokeAgentRuntime`, `CreateAgentRuntimeSession`, `TerminateAgentRuntimeSession`. Agent container images built by MIDAS CI/CD and pushed to **ECR**; AgentCore Runtime pulls from ECR and runs in isolated microVMs. |
| **Session management** | AgentCore microVM session per user conversation (`runtimeSessionId` = MIDAS `session_id`). Session TTL: idle 15 min, max 8 hours. On session end AgentCore sanitises microVM memory. Short-term turn context managed by AgentCore; cross-session facts persisted via AgentCore Memory API. |
| **Long-term memory** | AgentCore Memory API: automatically extracts and stores user preferences, dataset names, model choices, analysis history across sessions. Stored in AgentCore-managed store (PrivateLink). Agent reads memory at session start to personalise responses. |
| **Platform tools** | Every MIDAS service is wrapped as an MCP tool in `tools/`. Agent selects and calls tools via MCP over gRPC or REST to the tool-owning service. See §10.3 for the full tool catalogue. |
| **MIDAS RBAC integration** | Before invoking any platform tool, `authz_tool.py` calls `authz-service` `CheckPermission` gRPC to confirm the calling user has the required permission. Agents cannot bypass RBAC — they act on behalf of the authenticated user. |
| **State** | Agent definitions → **DynamoDB** `midas-agent-catalogue`. Agent run records → **DynamoDB** `midas-agent-runs`. Long-term memory → **AgentCore Memory** (managed, PrivateLink). Session short-term context → AgentCore microVM (ephemeral). Agent run artefacts → **S3 Files** `midas-agent-runs/` (referenced in `midas-agent-runs` DynamoDB). |
| **Streaming** | Responses streamed via SSE (HTTP) or WebSocket (AgentCore bidirectional). SSE is the default; WebSocket supported for interactive sessions requiring back-and-forth tool approval. |
| **Secrets** | AgentCore Outbound Auth credentials stored in **Secrets Manager** `/midas/agent-platform/agentcore-*`. MIDAS service calls use IRSA — agents inherit the pod's IAM role (`agent-platform-service-sa`). |
| **Portability** | AgentCore is AWS-specific. On Azure, replace with **Azure AI Foundry Agent Service** by swapping `agentcore_service.py` behind an `AgentRuntimePort` interface. Tool adapters are cloud-agnostic since they call MIDAS gRPC APIs. |

---

## 6. Authentication & Authorisation Deep-Dive

This section is a developer reference for the two-service auth model. Read this before writing any code that touches user identity, sessions, or permission checks.

### 6.1 Responsibility Boundary

```
┌──────────────────────────────────────────────────────────────────┐
│                        WHO IS THE USER?                          │
│                       identity-service                            │
│                                                                  │
│  Cognito Hosted UI ──► PKCE exchange ──► MIDAS session JWT       │
│  Token refresh ──► new session JWT                               │
│  Logout ──► Redis session deletion (immediate revocation)        │
│  /me ──► user profile from DynamoDB midas-users                  │
└──────────────────────────────────────────────────────────────────┘
                              │
                      JWT in every request
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│               WHAT IS THE USER ALLOWED TO DO?                    │
│                        authz-service                             │
│                                                                  │
│  POST /v1/authz/check {user_id, action, resource_type, id}       │
│  → Redis lookup (5-min TTL) or DynamoDB RBAC tables              │
│  → {allowed: true/false, reason: "..."}                          │
└──────────────────────────────────────────────────────────────────┘
```

**Rule:** `identity-service` never evaluates permissions. `authz-service` never issues tokens.

---

### 6.2 AWS Cognito Integration

```
                    Browser / API client
                           │
              GET /v1/identity/login-url
                           │
                    identity-service
                           │ builds Cognito Hosted UI URL
                           │ with PKCE code_challenge
                           ▼
              ┌────────────────────────┐
              │   AWS Cognito          │
              │   Hosted UI            │  (VPC-internal endpoint via PrivateLink)
              │   User Pool: midas-up  │
              └────────────────────────┘
                           │  redirect with ?code=...
                           ▼
              GET /v1/identity/callback?code=...
                    identity-service
                           │
                    exchange code → Cognito /token endpoint
                           │  receives: id_token, access_token, refresh_token
                           │
                    extract sub, email, groups from id_token
                           │
                    JIT provision user in DynamoDB midas-users
                           │
                    issue MIDAS session JWT (own key, short-lived)
                    store session in Redis session:{jti}
                    store refresh_token hash in DynamoDB midas-users
                           │
                    return MIDAS session JWT to client
```

**What the client holds:**
- `midas_session` (short-lived JWT, 1 hour) — sent as `Authorization: Bearer`
- `midas_rt` (httpOnly cookie, 8 hours) — used for silent refresh via `POST /v1/identity/refresh`

**What downstream services see:**
- Only the MIDAS session JWT — they never see Cognito tokens.
- JWT claims include: `sub` (MIDAS `user_id`), `email`, `groups` (Cognito groups mapped to MIDAS roles), `jti`, `exp`.

---

### 6.3 RBAC Model

```
Permission   ──────────────┐
(action + resource_type)   │
e.g. "dataset:upload"      │
                           ▼
                    Role definition
                    e.g. "analyst" = [dataset:upload, model:train, ...]
                           │
                           ▼
                    User-Role Assignment
                    {user_id, role_id, scope_type, scope_id}
                    e.g. user-123, analyst, project, proj-456
                           │
                           ▼
              authz-service.check(user_id, action, resource_type, resource_id)
                    → resolves effective permissions
                    → returns {allowed: bool, matched_role: str, reason: str}
```

**Scoped assignments** allow a user to be `analyst` on project A and `viewer` on project B without affecting other projects. `scope_type = "global"` means the role applies to all resources of that type.

---

### 6.4 DynamoDB Table Layout for Auth/Authz

| Table | PK | SK | Key attributes |
|---|---|---|---|
| `midas-users` | `user_id` | — | `email`, `cognito_sub`, `created_at`, `refresh_token_hash` |
| `midas-sessions` | `session_id` (= JWT `jti`) | — | `user_id`, `expires_at` (TTL), `issued_at` — also in Redis |
| `midas-roles` | `role_id` | — | `name`, `description`, `permissions` (list of strings) |
| `midas-permissions` | `permission_id` | — | `action`, `resource_type`, `description` |
| `midas-user-roles` | `user_id` | `role_id#scope_type#scope_id` | `assigned_at`, `assigned_by` |

---

### 6.5 Redis Key Layout for Auth/Authz

| Key | Value | TTL | Owned by |
|---|---|---|---|
| `session:{jti}` | JSON user context (`user_id`, `email`, `groups`) | Token expiry (1 hr) | `identity-service` |
| `authz:{user_id}:{resource_type}:{resource_id}` | JSON permission set for that user+resource | 5 min | `authz-service` |
| `authz:{user_id}:global` | JSON global permissions for user | 5 min | `authz-service` |

On logout: `identity-service` deletes `session:{jti}` immediately (token is revoked before natural expiry).  
On role change: `authz-service` deletes `authz:{user_id}:*` keys immediately (permissions are re-evaluated on next request).

---

### 6.6 Istio + authz-service Layering

```
Request arrives at service (e.g. dataset-service)
        │
        ▼
[Layer 1] Istio RequestAuthentication
  - Validates JWT signature using JWKS from identity-service
  - Rejects if token is expired or malformed
  - Sets x-jwt-payload header (base64 decoded claims)
        │
        ▼
[Layer 2] Service extracts user_id from x-jwt-payload header
  (no signature check needed — Istio already did it)
        │
        ▼
[Layer 3] Service calls authz-service
  POST /v1/authz/check {user_id, action, resource_type, resource_id}
  - authz-service checks Redis cache (5-min TTL)
  - Cache miss → DynamoDB RBAC lookup
  - Returns {allowed: bool}
        │
  allowed=false → 403 Forbidden
  allowed=true  → proceed with business logic
```

**No service implements its own permission check logic.** All use `AuthzClient` from `midas-common`.

---

### 6.7 Secrets for Identity Service

```
/midas/identity/cognito-user-pool-id        ← Cognito User Pool ID
/midas/identity/cognito-client-id           ← App client ID (public)
/midas/identity/cognito-client-secret       ← App client secret (confidential)
/midas/identity/cognito-domain              ← Cognito hosted UI domain
/midas/identity/jwt-signing-key             ← MIDAS session JWT HS256 key
/midas/identity/jwt-public-key-pem          ← Public key for JWKS endpoint
```

All fetched via `SecretsPort.get()` at Pod startup, cached in-process with 15-min TTL + automatic rotation support.

---

## 7. Data Fabric Deep-Dive

The `data-fabric-service` is a data-centric service — it does not contain analytics logic, training logic, or business rules. Its sole purpose is to create, store, version, and serve data objects reliably.

### 7.1 Responsibilities

```
┌──────────────────────────────────────────────────────────────────────┐
│                       data-fabric-service                            │
│                                                                      │
│  Ingest         ─  accept raw uploads (CSV, Parquet, Excel, etc.)    │
│  Store          ─  write raw to S3, processed to S3 Files            │
│  Version        ─  track dataset versions with ETags + timestamps    │
│  Transform ref  ─  store split configs, schema snapshots             │
│  Artefact reg   ─  receive and catalogue ML model files from runners  │
│  Serve          ─  return bytes or DataFrame (via Redis cache)        │
│  Catalogue      ─  DynamoDB index of all data objects + lineage       │
└──────────────────────────────────────────────────────────────────────┘
```

**Rule:** No service other than `data-fabric-service` holds a `StoragePort` instance that writes to the MIDAS data buckets. Other services call `data-fabric-service` over gRPC to store and retrieve data. This enforces single ownership and makes the data catalogue complete.

---

### 7.2 Storage Layout

| Store | Path | Content | Access pattern |
|---|---|---|---|
| **AWS S3** (standard) | `midas-raw/{dataset_id}/{version}/{filename}` | Original uploaded files | Write once on upload; rare reads |
| **AWS S3 Files** | `midas-datasets/parquet/{dataset_id}/{version}/{scope}.parquet` | Processed, split DataFrames | Frequent reads by analytics + computation |
| **AWS S3 Files** | `midas-datasets/splits/{dataset_id}/{version}/split_config.json` | Train/test split indices | Read on job start |
| **AWS S3 Files** | `midas-artefacts/{job_id}/{type}/{filename}` | Trained model pickles, SHAP outputs, feature importance files | Written by computation pods; read by evaluation + llm |
| **DynamoDB** `midas-data-catalogue` | — | All metadata: dataset items, version items, artefact items, lineage links | Key lookups + GSI queries |
| **ElastiCache Redis** | `df:{dataset_id}:{scope}:{version}` | LZ4-compressed parquet bytes (hot DataFrame cache) | Hot read path for analytics |

**Why S3 Files for processed data?**  
S3 Files provides byte-range reads and POSIX-like append semantics. ML libraries (`pandas`, `pyarrow`, `joblib`) can stream large parquet files without downloading the full object, reducing memory pressure in computation pods.

---

### 7.3 Data Catalogue DynamoDB Schema

Single-table design (`midas-data-catalogue`):

| Item type | PK | SK | Key attributes |
|---|---|---|---|
| `Dataset` | `DATASET#{dataset_id}` | `META` | `project_id`, `name`, `created_at`, `latest_version`, `schema_hash` |
| `DatasetVersion` | `DATASET#{dataset_id}` | `VERSION#{version}` | `raw_s3_key`, `parquet_s3_files_key`, `row_count`, `col_count`, `etag`, `created_at` |
| `Split` | `DATASET#{dataset_id}` | `SPLIT#{split_id}` | `version`, `train_ratio`, `test_ratio`, `split_config_s3_key`, `created_at` |
| `Artefact` | `ARTEFACT#{job_id}` | `TYPE#{artefact_type}` | `s3_files_key`, `dataset_id`, `pipeline_id`, `created_at`, `size_bytes` |
| `Lineage` | `DATASET#{dataset_id}` | `JOB#{job_id}` | `pipeline_id`, `artefact_ids`, `run_at` |

GSI `project-datasets-index`: PK = `project_id`, SK = `created_at` → list all datasets for a project.

---

### 7.4 gRPC API Contract (`data_fabric.proto`)

```protobuf
syntax = "proto3";
package midas.datafabric.v1;

service DataFabricService {
  rpc GetDataset        (GetDatasetRequest)     returns (DatasetMeta);
  rpc ListDatasets      (ListDatasetsRequest)   returns (ListDatasetsResponse);
  rpc GetDataframe      (GetDataframeRequest)   returns (DataframeBytes);
  rpc GetRawFile        (GetRawFileRequest)     returns (FileBytes);
  rpc RegisterArtefact  (RegisterArtefactRequest) returns (ArtefactRef);
  rpc GetArtefact       (GetArtefactRequest)    returns (FileBytes);
  rpc GetLineage        (GetLineageRequest)     returns (LineageGraph);
}

message GetDataframeRequest {
  string dataset_id = 1;
  string scope      = 2;   // "train", "test", "full"
  string version    = 3;   // empty = latest
}

message DataframeBytes {
  bytes  parquet_lz4 = 1;  // LZ4-compressed parquet; reconstruct with pd.read_parquet
  int64  row_count   = 2;
  int64  col_count   = 3;
  string etag        = 4;
}
```

---

## 8. Computation Service Deep-Dive (Kubeflow)

The `computation-service` replaces the current thread-based `training-orchestrator` + `training-worker` model with a first-class ML pipeline platform.

### 8.1 Architecture

```
                        REST/gRPC API
                              │
                              ▼
                   ┌─────────────────────┐
                   │  computation-service │  ← MIDAS facade (FastAPI + gRPC server)
                   │  (Kubernetes Pod)    │
                   └──────────┬──────────┘
                              │  Kubeflow Pipelines SDK
                              ▼
                   ┌─────────────────────┐
                   │  Kubeflow Pipelines  │  ← Runs in midas-pipelines namespace
                   │  (Argo Workflows)   │
                   └──────────┬──────────┘
                              │  spawns per-step pods
                              ▼
              ┌───────────────────────────────────┐
              │  midas-pipelines namespace         │
              │                                   │
              │  [data-ingestion-step pod]         │
              │  [feature-engineering-step pod]    │
              │  [model-training-step pod]         │
              │  [evaluation-step pod]             │
              └───────────────────────────────────┘
                              │
                   Each step pod calls:
                   - data-fabric-service (gRPC) for data in/out
                   - evaluation-service (gRPC) to record results
```

### 8.2 Core Concepts for Developers

| Concept | Definition | Stored in |
|---|---|---|
| **Component** | A reusable, versioned piece of computation (e.g. `LogisticRegressionTrainer`, `FeatureEngineer`, `RFESelector`). Defined as a Python function decorated with `@kfp.component`. | DynamoDB `midas-pipeline-catalogue`, PK: `COMPONENT#{id}` |
| **Pipeline** | A directed acyclic graph (DAG) of components with wired inputs/outputs. | DynamoDB `midas-pipeline-catalogue`, PK: `PIPELINE#{id}` |
| **Run** | An execution of a pipeline with a specific set of parameters (dataset_id, hyperparameters, etc.). | DynamoDB `midas-pipeline-runs` |
| **Function** | A primitive operation available to compose into components (add, transform, filter, aggregate). | Registered in DynamoDB; exposed via `GET /api/v1/computation/functions` |

### 8.3 Pipeline Catalogue API (Developer-facing)

All catalogue operations return JSON. Pipeline and component definitions are stored in DynamoDB; artefacts (compiled KFP YAML) in S3 Files.

```
CATALOGUE MANAGEMENT
─────────────────────────────────────────────────────────────────────
GET    /api/v1/computation/components              List all components
POST   /api/v1/computation/components              Register new component
GET    /api/v1/computation/components/{id}         Get component spec
PUT    /api/v1/computation/components/{id}         Edit component metadata
DELETE /api/v1/computation/components/{id}         Delete component

GET    /api/v1/computation/pipelines               List all pipelines
POST   /api/v1/computation/pipelines               Create pipeline (DAG spec)
GET    /api/v1/computation/pipelines/{id}          Get pipeline spec + version history
PUT    /api/v1/computation/pipelines/{id}          Edit pipeline (creates new version)
DELETE /api/v1/computation/pipelines/{id}          Delete pipeline

GET    /api/v1/computation/functions               List primitive functions

EXECUTION
─────────────────────────────────────────────────────────────────────
POST   /api/v1/computation/pipelines/{id}/runs     Trigger a pipeline run
GET    /api/v1/computation/runs/{id}               Get run status + step statuses
GET    /api/v1/computation/runs/{id}/stream        SSE stream of run progress events
POST   /api/v1/computation/runs/{id}/cancel        Cancel a running pipeline
GET    /api/v1/computation/runs/{id}/artefacts     List artefacts produced by run
```

### 8.4 Pipeline Definition Format (developer-authored)

Developers build pipelines by composing registered components. The `computation-service` compiles the definition to a Kubeflow Pipelines YAML and submits it to the Kubeflow API server.

```python
# Example: defining a model training pipeline via midas-common SDK helper
from midas.sdk.computation import Pipeline, ComponentRef

pipeline = Pipeline(
    name="logistic-regression-training",
    description="Full LR pipeline: feature engineering → RFE → training → MEEA",
    steps=[
        ComponentRef("feature-engineer-v2",   inputs={"dataset_id": "$.params.dataset_id"}),
        ComponentRef("rfe-selector-v1",        inputs={"dataset_id": "$.steps[0].output.dataset_id"}),
        ComponentRef("lr-trainer-v3",          inputs={"dataset_id": "$.steps[1].output.dataset_id",
                                                        "hyperparams": "$.params.hyperparams"}),
        ComponentRef("meea-evaluator-v1",      inputs={"model_artefact": "$.steps[2].output.model_ref"}),
    ]
)
```

### 8.5 Data Flow through Computation

```
1. POST /api/v1/computation/pipelines/{id}/runs
   {dataset_id: "ds-123", hyperparams: {...}}
        │
        ▼
2. computation-service validates params + authz
   Creates PipelineRun in DynamoDB (status=PENDING)
   Submits KFP PipelineRun to Kubeflow API server
        │
        ▼
3. Kubeflow/Argo Workflows schedules step pods in midas-pipelines ns
        │
        ▼
4. Each step pod:
   a. gRPC → data-fabric-service.GetDataframe(dataset_id, scope)
   b. Runs computation (CPU/memory bound, isolated pod)
   c. gRPC → data-fabric-service.RegisterArtefact(job_id, s3_key, type)
   d. Updates KFP run metadata (Kubeflow stores in its own DB)
        │
        ▼
5. computation-service polls KFP → updates DynamoDB midas-pipeline-runs
   Publishes SSE events to Redis pub/sub (train:progress:{run_id})
        │
        ▼
6. evaluation-service listens for run completion → fetches artefacts → stores MEEA
```

### 8.6 Namespace Layout for Kubeflow

```
eks-cluster: midas-eks
├── namespace: midas-system          ← Istio control plane
├── namespace: midas-services        ← All MIDAS microservices incl. computation-service
├── namespace: kubeflow              ← Kubeflow Pipelines control plane
│   ├── ml-pipeline                  ← KFP API server, persistence agent, UI
│   └── argo                         ← Argo Workflow controller
└── namespace: midas-pipelines       ← Pipeline step execution pods (ephemeral)
    ├── [feature-eng-step-pod]        ← spawned by Argo per run
    ├── [rfe-step-pod]
    └── [model-train-step-pod]
```

Step pods in `midas-pipelines` are ephemeral — they exist only for the duration of their pipeline step. They share the same IRSA service account (`pipeline-step-sa`) with permissions to read from `data-fabric-service` gRPC and write artefacts back.

---

## 9. ALB + WAF Ingress Layer

All web application traffic from browsers enters through a **private AWS Application Load Balancer (ALB)** with an **AWS WAF** web ACL attached. This is the security and routing boundary between the corporate network and the EKS cluster.

### 9.1 Traffic Flow

```
Corporate Network / Browser
        │
        │  HTTPS :443  (corporate DNS → NLB DNS alias)
        ▼
┌──────────────────────────────────────────────────────────────┐
│  AWS Network Load Balancer (NLB)  — TCP passthrough :443     │
│  (corporate DNS FQDN CNAMEs here; existing pattern from      │
│   deploy/ecs-app/alb-nlb.tf: NLB → ALB → EKS)               │
└────────────────────────┬─────────────────────────────────────┘
                         │  TCP :443
                         ▼
┌──────────────────────────────────────────────────────────────┐
│  AWS WAF Web ACL  (attached to the ALB)                      │
│                                                              │
│  Rules enforced (in order):                                  │
│  1. AWS Managed Rules — Common Rule Set (OWASP Top 10)       │
│  2. AWS Managed Rules — Known Bad Inputs                     │
│  3. Rate-based rule — 2000 req / 5 min per IP                │
│  4. Geo-block rule  — allow only corporate-approved regions  │
│  5. Custom rule     — block requests without valid JWT        │
│                       (pre-auth paths: /login, /health skip) │
└────────────────────────┬─────────────────────────────────────┘
                         │  HTTPS :443  (TLS terminates at ALB)
                         ▼
┌──────────────────────────────────────────────────────────────┐
│  AWS Internal ALB                                            │
│                                                              │
│  Listener rules (path-based routing):                        │
│  /api/*          → target group: istio-ingressgateway :80    │
│  /               → target group: istio-ingressgateway :80    │
│  /health         → target group: istio-ingressgateway :80    │
└────────────────────────┬─────────────────────────────────────┘
                         │  HTTP :80  (inside VPC — already TLS-terminated)
                         ▼
                Istio Ingress Gateway  (NodePort service)
                         │  mTLS inside mesh
                         ▼
               midas-services namespace (microservices)
```

### 9.2 ALB Configuration

The existing `deploy/ecs-app/alb-nlb.tf` Terraform module already provisions the NLB → ALB chain (confirmed from code). The future-state change is:

1. **Attach WAF Web ACL** to the ALB: new Terraform resource `aws_wafv2_web_acl_association`.
2. **Single target group** for all traffic: the ALB forwards everything to the Istio Ingress Gateway NodePort. Path-based routing (frontend vs backend vs API) moves inside Istio `VirtualService` rules.
3. **TLS terminates at the ALB**: ACM certificate (`var.alb_nlb_certificate_arn`). Traffic inside the VPC from ALB → Istio is HTTP (already the pattern in existing TF).
4. **WAF logging**: WAF logs ship to S3 bucket `midas-waf-logs/` via `aws_wafv2_web_acl_logging_configuration`. CloudWatch metric filters alert on spike in blocked requests.

### 9.3 WAF Rule Set (developer reference)

| Rule group | Type | Action | Notes |
|---|---|---|---|
| `AWSManagedRulesCommonRuleSet` | AWS Managed | Block | OWASP Top 10, SQL injection, XSS |
| `AWSManagedRulesKnownBadInputsRuleSet` | AWS Managed | Block | Log4j, path traversal, SSRF |
| `RateBasedByIP` | Custom rate-based | Block | 2000 req per 5 min per source IP |
| `GeoMatchBlock` | Custom geo match | Block | Block non-approved country codes |
| `RequireAuthHeader` | Custom regex | Block (allow: `/api/v1/identity/*`, `/health`) | Requests without `Authorization:` header blocked at WAF boundary |

### 9.4 Security Group Flow (from existing Terraform)

The existing pattern from `deploy/ecs-app/alb-nlb-eks-sg.tf`:
- NLB security group: ingress from `var.nlb_corporate_ingress_cidrs` (corporate CIDR ranges), egress to ALB.
- ALB security group: ingress from NLB only, egress to EKS node security group on port 30000–32767 (NodePort range for Istio gateway).
- WAF does not change security group rules — it sits logically in front of the ALB listener, not as a separate network hop.

### 9.5 Kubernetes Ingress (Istio Gateway)

All path routing from ALB inward is owned by Istio `Gateway` + `VirtualService` — not by Kubernetes `Ingress` objects. The ALB forwards blindly to the Istio NodePort; Istio does the path → service routing.

```yaml
# Istio Gateway (midas-system namespace) — illustrative
apiVersion: networking.istio.io/v1beta1
kind: Gateway
metadata:
  name: midas-gateway
  namespace: midas-system
spec:
  selector:
    istio: ingressgateway
  servers:
  - port:
      number: 80
      name: http
      protocol: HTTP
    hosts:
    - "*"
---
# VirtualService — routes /api/v1/* to the correct service
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: midas-routes
  namespace: midas-system
spec:
  hosts: ["*"]
  gateways: ["midas-gateway"]
  http:
  - match:
    - uri: { prefix: "/api/v1/identity" }
    route:
    - destination: { host: identity-service.midas-services.svc.cluster.local, port: { number: 8080 } }
  - match:
    - uri: { prefix: "/api/v1/data" }
    route:
    - destination: { host: data-fabric-service.midas-services.svc.cluster.local, port: { number: 8080 } }
  - match:
    - uri: { prefix: "/api/v1/computation" }
    route:
    - destination: { host: computation-service.midas-services.svc.cluster.local, port: { number: 8080 } }
  # ... other services ...
```

---

## 10. AI Agent Fabric Deep-Dive (AWS AgentCore)

This section is the developer reference for `agent-platform-service`. Read it before writing any code that touches agent creation, agent invocation, tool registration, or agent memory.

---

### 10.1 Architecture Overview

```
┌──────────────────────────────────────────────────────────────────────────┐
│                     agent-platform-service  (EKS Pod)                    │
│                                                                          │
│  ┌─────────────┐   ┌──────────────────┐   ┌──────────────────────────┐  │
│  │  REST API   │   │   gRPC Server    │   │    AgentCore SDK Layer   │  │
│  │  :8080      │   │   :50051         │   │    agentcore_service.py  │  │
│  │  agent_     │   │   InvokeAgent    │   │                          │  │
│  │  routes.py  │   │   StreamAgent    │   │  CreateAgentRuntime()    │  │
│  │  tool_      │   │   GetStatus      │   │  InvokeAgentRuntime()    │  │
│  │  routes.py  │   │   ListTools      │   │  CreateSession()         │  │
│  │  memory_    │   │                  │   │  TerminateSession()      │  │
│  │  routes.py  │   └──────────────────┘   │  Memory.store/retrieve() │  │
│  └─────────────┘                          └──────────────────────────┘  │
│                                                                          │
│  ┌────────────────────────────────────────────────────────────────────┐  │
│  │                    Tool Registry  (tool_registry.py)               │  │
│  │                                                                    │  │
│  │  data_fabric_tool  analytics_tool  computation_tool  llm_tool      │  │
│  │  graphrag_tool     evaluation_tool  project_tool     authz_tool    │  │
│  │                                                                    │  │
│  │  Each tool:  MCP ToolDefinition  +  Python adapter calling         │  │
│  │              the owning service's gRPC or REST interface           │  │
│  └────────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────────┘
         │                          │                        │
         ▼                          ▼                        ▼
┌──────────────┐    ┌───────────────────────────┐    ┌──────────────────┐
│  AgentCore   │    │  MIDAS microservices       │    │  DynamoDB        │
│  Runtime API │    │  (gRPC :50051)             │    │  midas-agent-    │
│  (PrivateLink│    │  data-fabric-service       │    │  catalogue       │
│  VPC endpoint│    │  analytics-service         │    │  midas-agent-    │
│  us-east-1)  │    │  computation-service       │    │  runs            │
│              │    │  llm-service               │    └──────────────────┘
│  Memory API  │    │  graphrag-service          │
│  (long-term) │    │  evaluation-service        │    ┌──────────────────┐
│              │    │  project-service           │    │  S3 Files        │
│  microVM     │    │  authz-service             │    │  midas-agent-    │
│  session     │    └───────────────────────────┘    │  runs/           │
│  isolation   │                                      └──────────────────┘
└──────────────┘
```

**Design rule:** `agent-platform-service` never speaks directly to DynamoDB, S3, or Redis on behalf of agent tasks. All data operations go through the owning service's gRPC API (data-fabric, analytics, computation, etc.). The service only writes to its own tables (`midas-agent-catalogue`, `midas-agent-runs`) and the AgentCore APIs.

---

### 10.2 AgentCore Abstraction Layer

AgentCore is AWS-specific. The abstraction isolates it behind `AgentRuntimePort` so a non-AWS provider can be swapped by changing the adapter only.

```python
# midas-common/midas/ports/agent_runtime.py
from abc import ABC, abstractmethod
from typing import AsyncIterator

class AgentRuntimePort(ABC):
    """Cloud-agnostic interface for a managed agent runtime."""

    @abstractmethod
    async def create_runtime(self, name: str, image_uri: str, tools: list[str]) -> str:
        """Register agent container image. Returns runtime_id."""

    @abstractmethod
    async def invoke(
        self, runtime_id: str, session_id: str, input_text: str, context: dict
    ) -> AsyncIterator[str]:
        """Invoke agent. Yields response chunks as they stream."""

    @abstractmethod
    async def create_session(self, runtime_id: str, session_id: str) -> str:
        """Create isolated session microVM. Returns session_arn."""

    @abstractmethod
    async def terminate_session(self, runtime_id: str, session_id: str) -> None:
        """Terminate microVM, sanitise memory."""

    @abstractmethod
    async def store_memory(self, user_id: str, facts: list[dict]) -> None:
        """Persist long-term memory facts for user."""

    @abstractmethod
    async def retrieve_memory(self, user_id: str, query: str) -> list[dict]:
        """Retrieve relevant long-term memory facts for context."""
```

```python
# services/agent-platform-service/app/services/agentcore_service.py
import boto3
from midas.ports.agent_runtime import AgentRuntimePort

class AgentCoreAdapter(AgentRuntimePort):
    """AWS Bedrock AgentCore implementation."""

    def __init__(self):
        self._runtime = boto3.client("bedrock-agentcore-runtime", region_name="us-east-1")
        self._control = boto3.client("bedrock-agentcore-control", region_name="us-east-1")
        self._memory  = boto3.client("bedrock-agentcore-memory",  region_name="us-east-1")

    async def invoke(self, runtime_id, session_id, input_text, context):
        response = self._runtime.invoke_agent_runtime(
            agentRuntimeId=runtime_id,
            runtimeSessionId=session_id,
            payload={"input": input_text, "context": context},
        )
        # Stream response chunks
        for event in response["stream"]:
            yield event["chunk"]["bytes"].decode()

    async def store_memory(self, user_id, facts):
        self._memory.create_memory_records(
            memoryId=f"midas-user-{user_id}",
            records=[{"content": f["content"], "type": f["type"]} for f in facts],
        )

    async def retrieve_memory(self, user_id, query):
        resp = self._memory.retrieve_memories(
            memoryId=f"midas-user-{user_id}",
            searchQuery=query,
            maxResults=10,
        )
        return resp.get("memories", [])
```

**Cloud portability note:** On Azure, replace `AgentCoreAdapter` with `AzureAIFoundryAgentAdapter` implementing the same `AgentRuntimePort`. No other file changes.

---

### 10.3 MIDAS Platform Tool Catalogue

Every tool below is an MCP `ToolDefinition` registered in `tool_registry.py`. Agents receive this list at session start and call tools by name. Each tool internally calls the corresponding MIDAS service gRPC API.

| Tool Name | Backed by | Transport | What the agent can do |
|---|---|---|---|
| `midas.data.upload` | `data-fabric-service` | gRPC `RegisterArtefact` | Upload or reference a dataset |
| `midas.data.get_dataset` | `data-fabric-service` | gRPC `GetDataset` | Get dataset metadata, schema, version |
| `midas.data.preview` | `data-fabric-service` | gRPC `GetDataframe(scope=preview)` | Preview first 100 rows of a dataset |
| `midas.data.list_datasets` | `data-fabric-service` | gRPC `ListDatasets` | List all datasets in a project |
| `midas.data.get_split` | `data-fabric-service` | gRPC `GetDataframe(scope=train\|test)` | Retrieve train or test split |
| `midas.analytics.run_qc` | `analytics-service` | gRPC `RunQC` | Run data quality checks on a dataset |
| `midas.analytics.run_dqs` | `analytics-service` | gRPC → REST | Run DQS scoring |
| `midas.analytics.correlations` | `analytics-service` | REST `POST /analytics/correlations` | Get correlation matrix |
| `midas.analytics.vif` | `analytics-service` | REST `POST /analytics/vif` | Detect multicollinearity |
| `midas.computation.list_pipelines` | `computation-service` | REST `GET /computation/pipelines` | List available ML pipelines |
| `midas.computation.run_pipeline` | `computation-service` | gRPC `SubmitRun` | Trigger a training pipeline run |
| `midas.computation.get_run_status` | `computation-service` | gRPC `GetRunStatus` | Poll pipeline run status |
| `midas.computation.list_components` | `computation-service` | REST `GET /computation/components` | Browse reusable pipeline components |
| `midas.llm.chat` | `llm-service` | gRPC `Chat(stream)` | Send a chat message, get streamed reply |
| `midas.llm.list_models` | `llm-service` | REST `GET /chat/models` | List available LLM models |
| `midas.graphrag.build` | `graphrag-service` | REST `POST /graphrag/build` | Build knowledge graph from a dataset |
| `midas.graphrag.query` | `graphrag-service` | gRPC `Query` | Query a knowledge graph |
| `midas.graphrag.vector_search` | `graphrag-service` | gRPC `VectorSearch` | Semantic vector search |
| `midas.evaluation.get_results` | `evaluation-service` | REST `GET /evaluation/{model_id}` | Retrieve model evaluation results |
| `midas.evaluation.compare` | `evaluation-service` | REST `GET /evaluation/{id}/compare` | Compare two model evaluations |
| `midas.project.list` | `project-service` | gRPC `ListProjectsForUser` | List user's projects |
| `midas.project.get` | `project-service` | gRPC `GetProject` | Get project details |
| `midas.auth.check_permission` | `authz-service` | gRPC `CheckPermission` | Verify user permission before acting |
| `midas.documentation.generate` | `documentation-service` | REST `POST /documentation/generate` | Generate model documentation |

**Tool adapter pattern (every tool follows this):**

```python
# services/agent-platform-service/app/tools/computation_tool.py
from midas.clients.computation import ComputationClient
from midas.clients.authz import AuthzClient
from midas.ports.agent_runtime import MCPToolDefinition

class ComputationRunPipelineTool:
    name = "midas.computation.run_pipeline"
    description = (
        "Trigger a MIDAS ML pipeline run. "
        "Provide pipeline_id, dataset_id, and hyperparams. "
        "Returns a run_id you can poll with midas.computation.get_run_status."
    )
    input_schema = {
        "type": "object",
        "required": ["pipeline_id", "dataset_id"],
        "properties": {
            "pipeline_id":  {"type": "string"},
            "dataset_id":   {"type": "string"},
            "split_id":     {"type": "string"},
            "hyperparams":  {"type": "object"},
        },
    }

    def __init__(self, computation_client: ComputationClient, authz_client: AuthzClient):
        self._comp  = computation_client
        self._authz = authz_client

    async def invoke(self, user_id: str, params: dict) -> dict:
        # RBAC gate — agent cannot bypass permissions
        check = await self._authz.check(
            user_id=user_id,
            action="computation:run-pipeline",
            resource_type="pipeline",
            resource_id=params["pipeline_id"],
        )
        if not check.allowed:
            return {"error": f"Permission denied: {check.reason}"}

        run_ref = await self._comp.submit_run(
            pipeline_id=params["pipeline_id"],
            dataset_id=params["dataset_id"],
            hyperparams=params.get("hyperparams", {}),
        )
        return {"run_id": run_ref.run_id, "status": "RUNNING"}

    def to_mcp(self) -> MCPToolDefinition:
        return MCPToolDefinition(name=self.name, description=self.description,
                                 input_schema=self.input_schema)
```

---

### 10.4 Agent Session Lifecycle

```
User / Web UI                 agent-platform-service           AgentCore Runtime
──────────────                ──────────────────────           ─────────────────
POST /agents/{id}/runs ──────► 1. validate JWT (identity)
  {input, session_id?}         2. authz check (agent:invoke)
                               3. lookup agent def in DynamoDB
                               4. CreateAgentRuntimeSession ──► microVM spawned
                                  (if new session_id)           isolated CPU/mem/fs
                               5. InvokeAgentRuntime ──────────► agent code executes
                                                                  tool calls → MIDAS gRPC
                               6. stream chunks back ◄──────────
                               7. DynamoDB midas-agent-runs
                                  status, tool_calls[], output
◄── SSE / WebSocket stream ───
    {step, tool, output, done}

              [next turn — same session_id]
POST /agents/{id}/runs ──────► InvokeAgentRuntime (same microVM, context preserved)
  {input, session_id: existing}

              [session ends — idle >15min or explicit terminate]
                               TerminateAgentRuntimeSession ──► microVM destroyed
                                                                  memory sanitised
                               AgentCore Memory API:
                                 extract_and_store(session_transcript)
                                 → long-term facts for user
```

**Session ID strategy:** MIDAS generates a `agent_session_id` = `{user_id}:{agent_id}:{uuid4}` on first invocation. The same ID is passed to all subsequent turns in the same conversation. The web UI stores it in session storage.

---

### 10.5 Long-Term Memory Model

```
Session 1 (user trains churn model)
  → AgentCore Memory extracts:
       {fact: "user prefers LightGBM over XGBoost", confidence: 0.9}
       {fact: "project 'telco-q2' contains churn dataset ds-001", confidence: 1.0}
       {fact: "target column is always 'churn'", confidence: 0.95}

Session 2 (user starts new training)
  → agent-platform-service calls retrieve_memory(user_id, query="training preferences")
  → AgentCore returns relevant facts
  → Agent pre-fills hyperparams with LightGBM, suggests ds-001, sets target="churn"
  → User only needs to confirm, not re-specify
```

Memory is stored in AgentCore's managed memory store accessed via VPC PrivateLink. The MIDAS service never reads or writes memory facts directly to DynamoDB or S3 — all memory operations go through the `AgentRuntimePort.store_memory` / `retrieve_memory` abstraction.

---

### 10.6 Out-of-the-Box Agent Definitions

Each agent definition is seeded into DynamoDB `midas-agent-catalogue` at deployment time.

| Agent ID | Name | Tools it uses | Trigger phrase |
|---|---|---|---|
| `data-qa-agent` | Data QA Agent | `midas.data.get_dataset`, `midas.analytics.run_qc`, `midas.analytics.run_dqs`, `midas.analytics.correlations`, `midas.analytics.vif` | "Run QC on my dataset" |
| `train-agent` | Model Training Agent | `midas.data.*`, `midas.analytics.run_qc`, `midas.computation.run_pipeline`, `midas.computation.get_run_status`, `midas.evaluation.get_results` | "Train a model on this data" |
| `insight-agent` | Data Insight Agent | `midas.llm.chat`, `midas.graphrag.query`, `midas.graphrag.vector_search`, `midas.analytics.*`, `midas.data.preview` | "Tell me about this dataset" |
| `doc-agent` | Documentation Agent | `midas.evaluation.get_results`, `midas.llm.chat`, `midas.documentation.generate`, `midas.data.get_dataset` | "Generate docs for this model" |
| `pipeline-builder-agent` | Pipeline Builder Agent | `midas.computation.list_pipelines`, `midas.computation.list_components`, `midas.computation.run_pipeline`, `midas.llm.chat` | "Help me build a training pipeline" |

---

### 10.7 DynamoDB Schema for AI Agent Fabric

**`midas-agent-catalogue`** — Agent definitions

| Attribute | Type | Description |
|---|---|---|
| `PK` | `AGENT#{agent_id}` | Partition key |
| `SK` | `VERSION#{version}` | Sort key — multiple versions per agent |
| `name` | String | Display name |
| `description` | String | What the agent does |
| `tools` | List\<String\> | Tool names from §10.3 |
| `framework` | String | `strands` \| `langgraph` \| `crewai` |
| `agentcore_runtime_id` | String | AgentCore Runtime ARN |
| `ecr_image_uri` | String | Container image |
| `created_by` | String | `user_id` (system for OOB agents) |
| `is_ootb` | Boolean | True for out-of-the-box agents |
| `status` | String | `ACTIVE` \| `DRAFT` \| `DEPRECATED` |

**`midas-agent-runs`** — Agent run records

| Attribute | Type | Description |
|---|---|---|
| `PK` | `RUN#{run_id}` | Partition key |
| `SK` | `AGENT#{agent_id}` | Sort key |
| `user_id` | String | Who invoked |
| `session_id` | String | AgentCore session ID |
| `status` | String | `RUNNING` \| `COMPLETE` \| `FAILED` \| `CANCELLED` |
| `input` | String | User's initial input |
| `tool_calls` | List\<Object\> | `[{tool, params, result, timestamp}]` |
| `output` | String | Final agent response |
| `started_at` | ISO-8601 | |
| `completed_at` | ISO-8601 | |
| `artefact_refs` | List\<String\> | S3 Files keys of run outputs |
| GSI | `USER_RUNS` on `user_id` | Query all runs for a user |

---

### 10.8 IRSA and IAM for AgentCore

`agent-platform-service` requires additional IAM permissions beyond standard MIDAS services. These are granted via IRSA to the `agent-platform-service-sa` Kubernetes service account.

```hcl
# deploy/ecs-app/modules/agent-platform/iam.tf
resource "aws_iam_policy" "agent_platform" {
  name = "midas-agent-platform-policy"
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AgentCoreRuntime"
        Effect = "Allow"
        Action = [
          "bedrock-agentcore:CreateAgentRuntime",
          "bedrock-agentcore:InvokeAgentRuntime",
          "bedrock-agentcore:CreateAgentRuntimeSession",
          "bedrock-agentcore:TerminateAgentRuntimeSession",
          "bedrock-agentcore:GetAgentRuntime",
          "bedrock-agentcore:UpdateAgentRuntime",
        ]
        Resource = "arn:aws:bedrock-agentcore:us-east-1:*:agent-runtime/midas-*"
      },
      {
        Sid    = "AgentCoreMemory"
        Effect = "Allow"
        Action = [
          "bedrock-agentcore:CreateMemoryRecord",
          "bedrock-agentcore:RetrieveMemories",
          "bedrock-agentcore:DeleteMemoryRecord",
        ]
        Resource = "arn:aws:bedrock-agentcore:us-east-1:*:memory/midas-*"
      },
      {
        Sid    = "ECRPull"
        Effect = "Allow"
        Action = ["ecr:GetDownloadUrlForLayer", "ecr:BatchGetImage", "ecr:BatchCheckLayerAvailability"]
        Resource = "arn:aws:ecr:us-east-1:*:repository/midas-agents/*"
      },
      {
        Sid    = "DynamoDB"
        Effect = "Allow"
        Action = ["dynamodb:PutItem", "dynamodb:GetItem", "dynamodb:UpdateItem",
                  "dynamodb:Query", "dynamodb:DeleteItem"]
        Resource = [
          "arn:aws:dynamodb:us-east-1:*:table/midas-agent-catalogue",
          "arn:aws:dynamodb:us-east-1:*:table/midas-agent-runs",
          "arn:aws:dynamodb:us-east-1:*:table/midas-agent-runs/index/*",
        ]
      }
    ]
  })
}
```

---

## 11. Data & Storage Strategy

### 12.1 DynamoDB Table Design

| Table | Partition Key | Sort Key | Purpose |
|---|---|---|---|
| `midas-users` | `user_id` | — | User records, Cognito `sub`, refresh token hashes — owned by `identity-service` |
| `midas-sessions` | `session_id` | — | Session metadata (TTL attribute for auto-expiry) — also mirrored in Redis — owned by `identity-service` |
| `midas-roles` | `role_id` | — | Named role definitions + permission lists — owned by `authz-service` |
| `midas-permissions` | `permission_id` | — | Canonical permission catalogue (`action` + `resource_type`) — owned by `authz-service` |
| `midas-user-roles` | `user_id` | `role_id#scope_type#scope_id` | User-to-role assignments with optional resource scope — owned by `authz-service` |
| `midas-projects` | `project_id` | — | Project CRUD; GSI: `user_id-index` |
| `midas-data-catalogue` | `DATASET#{dataset_id}` or `ARTEFACT#{job_id}` | `META` / `VERSION#{v}` / `SPLIT#{id}` / `TYPE#{type}` | All dataset versions, splits, artefacts, lineage — owned by `data-fabric-service` |
| `midas-messages` | `session_id` | `message_seq` | Conversation history (replaces `message_states` Postgres table) |
| `midas-pipeline-catalogue` | `PIPELINE#{id}` or `COMPONENT#{id}` | `META` / `VERSION#{v}` | Pipeline and component definitions — owned by `computation-service` |
| `midas-pipeline-runs` | `run_id` | — | Pipeline run status, step statuses, artefact refs — owned by `computation-service` |
| `midas-evaluations` | `model_id` | `eval_type` | MEEA payloads (S3 key reference) |
| `midas-doc-jobs` | `job_id` | — | Documentation generation status |
| `midas-analytics-results` | `dataset_id` | `analysis_type#run_id` | QC/DQS/correlation results |
| `midas-graphrag-meta` | `dataset_id` | `kg_version` | KG build metadata, S3 keys |
| `midas-agent-catalogue` | `AGENT#{agent_id}` | `VERSION#{v}` | Agent definitions, tool lists, AgentCore runtime ARN — owned by `agent-platform-service` |
| `midas-agent-runs` | `RUN#{run_id}` | `AGENT#{agent_id}` | Agent run records, tool_calls[], output, status — GSI on `user_id` |

**Replacing SQLite/Postgres `message_states`:** The current `message_states` table stores pickled DataFrames up to 50 MiB. In the future state, **DataFrames are never stored in any database** — they live in S3 (parquet) and Redis (hot cache). `midas-messages` stores only JSON-serialisable conversation and modelling metadata.

### 12.2 S3 Bucket Layout (AWS S3 Files)

```
midas-datasets/
  raw/{dataset_id}/{filename}
  parquet/{dataset_id}/{scope}.parquet      ← canonical working copy
  splits/{dataset_id}/split_config.json

midas-artefacts/
  models/{job_id}/{model_type}.pkl
  meea/{model_id}/{eval_type}.json.gz

midas-documentation/
  {job_id}/{filename}.docx

midas-knowledge-graphs/
  {dataset_id}/{kg_version}/graph.graphml
  {dataset_id}/{kg_version}/cache/

midas-logs/
  structured/{service}/{date}/...
```

**Why S3 Files (new AWS service)?** S3 Files adds POSIX-style file operations and byte-range access on top of S3 objects, enabling ML libraries to stream large parquet files and model pickles without full-object downloads. This is the preferred integration point for pandas `read_parquet(s3://...)` and joblib `load(s3://...)` patterns in the worker pods.

### 12.3 Data Access Decision Tree

```
Need to read data in a request handler?
├── Is it a small metadata record (<100 KB)?         → DynamoDB
├── Is it a hot analytical record (re-read < 30 min)?→ Redis (CachePort) → S3 fallback
├── Is it a binary blob (model, parquet, docx)?       → S3 Files (StoragePort)
└── Is it conversation history?                        → DynamoDB (midas-messages)

Never:
  ├── SQLite files
  ├── Local disk write from a pod
  └── DataFrame in Pod process memory beyond request scope
```

---

## 12. Cross-Cutting Abstractions

This is the **portability layer** — the code that insulates all services from AWS-specific SDKs.

### 13.1 Package Structure

```
midas-common/                        ← shared Python package (published to internal PyPI / installed in all service images)
├── midas/
│   ├── ports/
│   │   ├── storage.py              ← StoragePort (ABC)
│   │   ├── cache.py                ← CachePort (ABC)
│   │   ├── secrets.py              ← SecretsPort (ABC)
│   │   ├── queue.py                ← QueuePort (ABC)
│   │   └── nosql.py                ← NoSQLPort (ABC)
│   ├── proto/                       ← .proto files + generated gRPC stubs
│   │   ├── identity/
│   │   │   └── identity.proto      ← VerifyToken, GetUser
│   │   ├── authz/
│   │   │   └── authz.proto         ← CheckPermission, GetUserPermissions, AssignRole
│   │   ├── dataset/
│   │   │   └── dataset.proto       ← GetDataset, GetDataframe, ListDatasets
│   │   ├── analytics/
│   │   │   └── analytics.proto     ← RunQC, RunDQS, GetResult
│   │   ├── training/
│   │   │   └── training.proto      ← StartJob, GetJobStatus, StreamProgress
│   │   └── llm/
│   │       └── llm.proto           ← Chat, GetModels (internal only)
│   ├── clients/                     ← pre-built gRPC client wrappers (used by all services)
│   │   ├── identity.py             ← IdentityClient(grpc_channel)
│   │   ├── authz.py                ← AuthzClient(grpc_channel)
│   │   └── dataset.py              ← DatasetClient(grpc_channel)
│   ├── adapters/
│   │   ├── aws/
│   │   │   ├── s3_storage.py       ← S3StorageAdapter(StoragePort)
│   │   │   ├── redis_cache.py      ← ElastiCacheRedisAdapter(CachePort)
│   │   │   ├── secrets_manager.py  ← SecretsManagerAdapter(SecretsPort)
│   │   │   ├── sqs_queue.py        ← SQSQueueAdapter(QueuePort)
│   │   │   └── dynamodb_nosql.py   ← DynamoDBAdapter(NoSQLPort)
│   │   ├── azure/                   ← (future) BlobStorage, CosmosDB, etc.
│   │   └── gcp/                     ← (future) GCS, Firestore, Memorystore
│   └── factory.py                   ← get_storage(), get_cache(), get_secrets(), get_queue(), get_nosql()
```

### 13.2 Port Interface Definitions

```python
# midas/ports/storage.py
from abc import ABC, abstractmethod

class StoragePort(ABC):
    @abstractmethod
    async def get(self, key: str) -> bytes: ...

    @abstractmethod
    async def put(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> None: ...

    @abstractmethod
    async def delete(self, key: str) -> None: ...

    @abstractmethod
    async def exists(self, key: str) -> bool: ...

    @abstractmethod
    async def list(self, prefix: str) -> list[str]: ...
```

```python
# midas/ports/cache.py
from abc import ABC, abstractmethod
from typing import Optional

class CachePort(ABC):
    @abstractmethod
    async def get(self, key: str) -> Optional[bytes]: ...

    @abstractmethod
    async def set(self, key: str, value: bytes, ttl: int = 300) -> None: ...

    @abstractmethod
    async def delete(self, key: str) -> None: ...

    @abstractmethod
    async def exists(self, key: str) -> bool: ...
```

```python
# midas/ports/nosql.py
from abc import ABC, abstractmethod
from typing import Any, Optional

class NoSQLPort(ABC):
    @abstractmethod
    async def get(self, table: str, key: dict) -> Optional[dict[str, Any]]: ...

    @abstractmethod
    async def put(self, table: str, item: dict[str, Any]) -> None: ...

    @abstractmethod
    async def update(self, table: str, key: dict, updates: dict[str, Any]) -> None: ...

    @abstractmethod
    async def delete(self, table: str, key: dict) -> None: ...

    @abstractmethod
    async def query(self, table: str, index: str, expression: str, values: dict) -> list[dict]: ...
```

```python
# midas/ports/secrets.py
from abc import ABC, abstractmethod

class SecretsPort(ABC):
    @abstractmethod
    async def get(self, name: str) -> str: ...          # returns plain string
    @abstractmethod
    async def get_json(self, name: str) -> dict: ...    # parses JSON string
```

```python
# midas/ports/queue.py
from abc import ABC, abstractmethod
from typing import Any

class QueuePort(ABC):
    @abstractmethod
    async def publish(self, queue_name: str, message: dict[str, Any]) -> str: ...  # returns message_id

    @abstractmethod
    async def receive(self, queue_name: str, max_messages: int = 10) -> list[dict]: ...

    @abstractmethod
    async def delete_message(self, queue_name: str, receipt_handle: str) -> None: ...
```

### 13.3 Factory (dependency injection entry point)

```python
# midas/factory.py
import os
from midas.ports.storage import StoragePort
from midas.ports.cache import CachePort

def get_storage() -> StoragePort:
    provider = os.environ.get("MIDAS_CLOUD_PROVIDER", "aws")
    if provider == "aws":
        from midas.adapters.aws.s3_storage import S3StorageAdapter
        return S3StorageAdapter(bucket=os.environ["S3_BUCKET"])
    elif provider == "azure":
        from midas.adapters.azure.blob_storage import BlobStorageAdapter
        return BlobStorageAdapter(...)
    elif provider == "gcp":
        from midas.adapters.gcp.gcs_storage import GCSStorageAdapter
        return GCSStorageAdapter(...)
    raise ValueError(f"Unknown provider: {provider}")
```

**Services never import from `midas.adapters.*` directly.** They import from `midas.factory` only. Switching cloud = changing `MIDAS_CLOUD_PROVIDER` env var + deploying the relevant adapter image layer.

---

## 13. Infrastructure Topology (EKS + Istio)

### 14.1 Kubernetes Namespaces

```
eks-cluster: midas-eks
├── namespace: midas-system        ← Istio control plane (istiod), ingress gateway
├── namespace: midas-services      ← All application microservice pods
├── namespace: midas-workers       ← (legacy placeholder — superseded by midas-pipelines)
├── namespace: kubeflow            ← Kubeflow Pipelines control plane + Argo Workflow controller
├── namespace: midas-pipelines     ← Ephemeral computation step pods (Argo Workflows)
└── namespace: midas-infra         ← Redis (if self-hosted), monitoring (Prometheus/Grafana)
```

### 14.2 Pod Design per Service

Every service follows this Kubernetes pattern:

```yaml
# Example: dataset-service deployment (illustrative)
apiVersion: apps/v1
kind: Deployment
metadata:
  name: dataset-service
  namespace: midas-services
spec:
  replicas: 2
  template:
    metadata:
      labels:
        app: dataset-service
        version: v1
      annotations:
        sidecar.istio.io/inject: "true"           # Istio sidecar
    spec:
      serviceAccountName: dataset-service-sa      # IRSA — no AWS keys in pod
      containers:
      - name: dataset-service
        image: <ecr-url>/midas/dataset-service:latest
        env:
        - name: MIDAS_CLOUD_PROVIDER
          value: "aws"
        - name: S3_BUCKET
          value: "midas-datasets"
        - name: SECRETS_PROVIDER
          value: "aws-secrets-manager"
        - name: SECRET_REF_REDIS
          value: "/midas/elasticache/connection-string"
        - name: SECRET_REF_DYNAMODB_TABLE
          value: "/midas/dynamodb/datasets-table"
        resources:
          requests:
            cpu: "250m"
            memory: "512Mi"
          limits:
            cpu: "2000m"
            memory: "4Gi"
        readinessProbe:
          httpGet:
            path: /health
            port: 8000
```

### 14.3 IRSA (IAM Roles for Service Accounts)

No AWS credentials in pod environment variables. Each service has a dedicated IAM role with **least-privilege** policy attached via IRSA:

| Service Account | IAM permissions |
|---|---|
| `identity-service-sa` | Secrets Manager read (`/midas/identity/*`), DynamoDB `midas-users`, `midas-sessions` (r/w), ElastiCache (VPC) |
| `authz-service-sa` | DynamoDB `midas-roles`, `midas-permissions`, `midas-user-roles` (r/w), ElastiCache (VPC) |
| `data-fabric-service-sa` | S3 `midas-raw` (r/w), S3 Files `midas-datasets`, `midas-artefacts` (r/w), DynamoDB `midas-data-catalogue` (r/w), ElastiCache (VPC) |
| `computation-service-sa` | Kubeflow API server (cluster internal), DynamoDB `midas-pipeline-catalogue`, `midas-pipeline-runs` (r/w), Secrets Manager read (`/midas/computation/*`) |
| `pipeline-step-sa` | gRPC to `data-fabric-service` (cluster internal), DynamoDB `midas-pipeline-runs` (write status only) |
| `llm-service-sa` | Secrets Manager read (`/midas/llm/*`), DynamoDB `midas-messages` (r/w), ElastiCache |

### 14.4 Istio Service Mesh

```
External Request
       │
       ▼
┌──────────────────┐
│  Istio Ingress   │  (internal ALB → NodePort → istio-ingressgateway)
│  Gateway         │
└────────┬─────────┘
         │  mTLS inside mesh
         ▼
┌─────────────────────────────────────────────────────────────┐
│                    midas-services namespace                  │
│                                                             │
│  ┌─────────────┐    ┌──────────────┐   ┌────────────────┐  │
│  │identity-svc │    │ authz-service│   │project-service │  │
│  │  :8080/:50051    │   :8080/:50051    │   :8080/:50051 │  │
│  └─────────────┘    └──────────────┘   └────────────────┘  │
│                                                             │
│  ┌─────────────┐    ┌──────────────┐   ┌────────────────┐  │
│  │data-fabric  │    │analytics-svc │   │graphrag-service│  │
│  │  :8080/:50051    │   :8080/:50051    │   :8080/:50051 │  │
│  └─────────────┘    └──────────────┘   └────────────────┘  │
│                                                             │
│  ┌─────────────────────┐   ┌────────────────────────────┐  │
│  │computation-service  │   │documentation-service       │  │
│  │  :8080/:50051       │   │   :8080/:50051             │  │
│  └─────────────────────┘   └────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
         │
         ▼  (mTLS, separate namespace)
┌────────────────────────────────────────────┐
│  kubeflow + midas-pipelines namespaces      │
│  Argo step pods (ephemeral, per pipeline)  │  ← Kubeflow Workflows
└────────────────────────────────────────────┘
```

**Istio policies in use:**

- `PeerAuthentication`: STRICT mTLS in `midas-services` and `midas-workers` namespaces — applies to both gRPC (:50051) and REST (:8080) ports transparently.
- `RequestAuthentication`: JWT validation for Cognito JWKS on all services' REST ports (:8080) at the Ingress Gateway. Internal gRPC calls carry the JWT as a metadata header (`authorization: bearer <token>`) — Istio validates it on internal hops too.
- `AuthorizationPolicy`: Service-to-service allow-list (e.g. only `analytics-service` can call `dataset-service` on port 50051; only `training-orchestrator` can call `training-worker`).
- `VirtualService` / `DestinationRule`: Retry (3×, 500ms base), circuit breaker (5 consecutive 5xx → open), timeout (30s default REST; 300s for streaming; 600s for gRPC training streams). Istio handles HTTP/2 framing for gRPC automatically — no per-service configuration needed.
- **Dual-port service definition** per Kubernetes `Service` object: port `8080` labelled `http` (REST), port `50051` labelled `grpc` — Istio uses these labels for correct protocol detection.

---

## 14. Inter-Service Communication Patterns

### Communication boundary rule

```
┌──────────────────────────────────────────────────────────────────┐
│  OUTSIDE the cluster (browser, frontend, CLI, 3rd-party)         │
│                                                                  │
│        RESTful HTTP/1.1 + JSON  (via Istio Ingress Gateway)      │
│                                                                  │
├──────────────────────────────────────────────────────────────────┤
│  INSIDE the mesh  (service → service within EKS)                 │
│                                                                  │
│        gRPC  (HTTP/2 + Protocol Buffers, mTLS via Istio)         │
└──────────────────────────────────────────────────────────────────┘
```

A service has **two ports**:

| Port | Protocol | When used |
|---|---|---|
| `:8080` | REST JSON (HTTP/1.1) | Exposed externally via Istio Ingress Gateway only |
| `:50051` | gRPC (HTTP/2) | Used exclusively for in-mesh service-to-service calls |

The Istio Ingress Gateway terminates REST and forwards internally. No external caller ever reaches a service's gRPC port directly.

---

### 12.1 Internal — gRPC (service → service)

All calls **between** MIDAS microservices inside the cluster use gRPC.

**Why gRPC internally:**
- Strongly-typed contracts via `.proto` files — breaking changes are caught at compile time, not runtime.
- HTTP/2 multiplexing — lower latency for the high-frequency `authz.check` and `dataset.getDataframe` calls.
- Built-in bidirectional streaming — used by `training-worker` to stream progress events back to `training-orchestrator`.
- Istio handles mTLS transparently on every gRPC connection — no per-service TLS code.

**Proto contract location:**

```
midas-common/
└── midas/
    └── proto/
        ├── identity/
        │   └── identity.proto        ← VerifyToken, GetUser RPCs
        ├── authz/
        │   └── authz.proto           ← CheckPermission, GetUserPermissions RPCs
        ├── dataset/
        │   └── dataset.proto         ← GetDataset, GetDataframe, ListDatasets RPCs
        ├── analytics/
        │   └── analytics.proto       ← RunQC, RunDQS, GetResult RPCs
        ├── training/
        │   └── training.proto        ← StartJob, GetJobStatus, StreamProgress RPCs
        └── llm/
            └── llm.proto             ← Chat, GetModels RPCs (internal only)
```

Generated stubs are published as part of `midas-common` and installed in every service image. Service teams own their `.proto` — changes go through a PR review on `midas-common` before any service can consume them.

**Example proto definition (`authz.proto`):**

```protobuf
syntax = "proto3";
package midas.authz.v1;

service AuthzService {
  rpc CheckPermission (CheckPermissionRequest) returns (CheckPermissionResponse);
  rpc GetUserPermissions (GetUserPermissionsRequest) returns (GetUserPermissionsResponse);
  rpc AssignRole (AssignRoleRequest) returns (AssignRoleResponse);
}

message CheckPermissionRequest {
  string user_id       = 1;
  string action        = 2;   // e.g. "dataset:upload"
  string resource_type = 3;   // e.g. "project"
  string resource_id   = 4;   // e.g. "proj-456"
}

message CheckPermissionResponse {
  bool   allowed      = 1;
  string matched_role = 2;
  string reason       = 3;
}
```

**Example gRPC call from `dataset-service`:**

```python
# dataset-service calls authz-service over gRPC (no REST)
import grpc
from midas.proto.authz.v1 import authz_pb2, authz_pb2_grpc

channel = grpc.aio.insecure_channel(
    "authz-service.midas-services.svc.cluster.local:50051"
    # Istio sidecar intercepts and upgrades to mTLS — insecure_channel is correct here
)
stub = authz_pb2_grpc.AuthzServiceStub(channel)

response = await stub.CheckPermission(authz_pb2.CheckPermissionRequest(
    user_id="user-123",
    action="dataset:upload",
    resource_type="project",
    resource_id="proj-456",
))
if not response.allowed:
    raise PermissionDeniedError(response.reason)
```

**Service-to-service DNS (gRPC):**

```
grpc://authz-service.midas-services.svc.cluster.local:50051
grpc://dataset-service.midas-services.svc.cluster.local:50051
grpc://identity-service.midas-services.svc.cluster.local:50051
```

---

### 12.2 External — REST JSON (client → cluster)

All calls **from outside the cluster** (frontend SPA, CLI, API consumers) use the REST API exposed at the Istio Ingress Gateway. The gateway translates incoming REST requests and routes them to the appropriate service's REST port (`:8080`). Services process the REST request internally and may then make downstream gRPC calls to other services.

```
External client (browser / CLI)
        │
        │  HTTPS  REST JSON
        ▼
Istio Ingress Gateway  :443
        │
        │  HTTP/1.1 REST  (to service :8080)
        ▼
Service REST handler
        │
        │  gRPC  (to peer services :50051)
        ▼
Peer services (identity, authz, dataset, ...)
```

**External REST API conventions:**

| Convention | Detail |
|---|---|
| Base path | `/api/v1/` |
| Auth | `Authorization: Bearer <midas-session-jwt>` |
| Content type | `application/json` |
| Errors | RFC 7807 Problem Details (`application/problem+json`) |
| Pagination | Cursor-based (`?cursor=<token>&limit=N`) |
| Streaming | Server-Sent Events (`text/event-stream`) for long-running progress |
| Versioning | URL-segment versioning (`/v1/`, `/v2/`). Additive changes are non-breaking; field removal requires a new version. |

**Explicit list of REST-only endpoints (external boundary):**

| Service | External REST endpoints |
|---|---|
| `identity-service` | `GET /api/v1/identity/login-url`, `GET /api/v1/identity/callback`, `POST /api/v1/identity/refresh`, `POST /api/v1/identity/logout`, `GET /api/v1/identity/me`, `GET /api/v1/identity/jwks` |
| `authz-service` | `GET /api/v1/authz/roles`, `POST /api/v1/authz/roles`, `PUT /api/v1/authz/users/{id}/roles`, `GET /api/v1/authz/users/{id}/permissions` |
| `project-service` | `GET/POST /api/v1/projects`, `GET/PUT/DELETE /api/v1/projects/{id}` |
| `dataset-service` | `POST /api/v1/datasets/upload`, `GET /api/v1/datasets`, `GET /api/v1/datasets/{id}`, `POST /api/v1/datasets/{id}/split` |
| `analytics-service` | `POST /api/v1/analytics/qc`, `POST /api/v1/analytics/dqs`, `POST /api/v1/analytics/correlations` |
| `llm-service` | `POST /api/v1/chat/completions`, `POST /api/v1/chat/agent`, `GET /api/v1/chat/models` |
| `training-orchestrator` | `POST /api/v1/training/start`, `GET /api/v1/training/{id}/status`, `GET /api/v1/training/{id}/stream` (SSE) |
| `documentation-service` | `POST /api/v1/documentation/generate`, `GET /api/v1/documentation/{id}/download` |
| `evaluation-service` | `GET /api/v1/evaluation/{model_id}`, `POST /api/v1/evaluation` |
| `graphrag-service` | `POST /api/v1/graphrag/build`, `POST /api/v1/graphrag/query` |

**`authz-service` internal gRPC only — no external `POST /check`:**  
The permission-check RPC (`CheckPermission`) is intentionally **not** exposed externally. External consumers manage roles via the REST admin endpoints; only other services call `CheckPermission` over gRPC.

---

### 12.3 Asynchronous — SQS Events (fire-and-forget / worker dispatch)

Used for **long-running work** (>3 seconds by rule). Not a transport choice — this is the pattern for work that must survive pod restarts.

```
training-orchestrator ──gRPC publish via SQSQueuePort──► SQS: midas-training-queue
                                              │
                                              ▼ (KEDA triggers scale-up)
                                   training-worker (×N Pods)
                                        │
                                        ├── gRPC → dataset-service (get DataFrame)
                                        ├── run training pipeline
                                        ├── write artefacts to S3
                                        └── gRPC → update DynamoDB job status
                                              │
                                              ▼ (SNS / EventBridge event)
                              ◄── evaluation-service listens for training.completed
```

**Event envelope (all SQS messages):**

```json
{
  "event_type": "training.started",
  "event_version": "1",
  "source_service": "training-orchestrator",
  "timestamp": "2026-04-28T09:00:00Z",
  "correlation_id": "req-abc-123",
  "payload": { ... }
}
```

---

### 12.4 SSE Streaming (external only)

SSE (`text/event-stream`) is a REST-boundary concern. It is served via the Istio Ingress Gateway to external clients only. Internally, the service driving the SSE stream subscribes to a Redis pub/sub channel (`training:progress:{job_id}`) that workers publish to over gRPC/Redis — the SSE endpoint is a fan-out bridge from internal Redis events to the external HTTP stream.

---

## 15. Cloud-Portability Abstraction Layer

The following table shows what changes when moving clouds — **no application code changes required**:

| Concern | AWS (current target) | Azure (future option) | GCP (future option) |
|---|---|---|---|
| Object storage | S3 + S3 Files | Azure Blob Storage | Google Cloud Storage |
| NoSQL database | DynamoDB | Azure Cosmos DB (NoSQL API) | Google Firestore |
| Cache | ElastiCache Redis | Azure Cache for Redis | Cloud Memorystore (Redis) |
| Queue | SQS | Azure Service Bus | Google Cloud Pub/Sub |
| Secrets | Secrets Manager | Azure Key Vault | GCP Secret Manager |
| Container platform | EKS | AKS | GKE |
| Service mesh | Istio (same) | Istio (same) | Istio (same) |
| Autoscaler | KEDA (same) | KEDA (same) | KEDA (same) |

**What switches per environment:**

1. `MIDAS_CLOUD_PROVIDER` env var (e.g. `"aws"`, `"azure"`, `"gcp"`)
2. The adapter package installed in the image (e.g. `midas-adapters-aws`, `midas-adapters-azure`)
3. IRSA / Workload Identity / Workload Identity Federation annotations on service accounts

**What never changes:**

- Service code (`routes.py`, service classes, domain logic)
- Port interfaces (`StoragePort`, `CachePort`, etc.)
- Kubernetes manifests (except service account annotations)
- Istio policies

### 12.1 DynamoDB Portability Note

DynamoDB has no direct equivalent on Azure or GCP with identical API. The `NoSQLPort` abstraction covers the common subset (get/put/update/delete/query-by-index). **Complex DynamoDB features (transactions, streams, conditional expressions) must be expressed through `NoSQLPort` — never via raw `boto3.resource('dynamodb')` in service code.** Adapter implementations handle the translation to Cosmos DB Change Feed or Firestore Transactions.

---

## 16. Secret Management

**Rule:** No secret value ever appears in a Docker image, Kubernetes manifest, git history, or environment variable passed via plain-text.

### 13.1 Secret Naming Convention in Secrets Manager

```
/midas/{service}/{secret-name}

Examples:
  /midas/identity/cognito-user-pool-id
  /midas/identity/cognito-client-id
  /midas/identity/cognito-client-secret
  /midas/identity/cognito-domain
  /midas/identity/jwt-signing-key
  /midas/identity/jwt-public-key-pem
  /midas/llm/gateway-virtual-key
  /midas/elasticache/connection-string
  /midas/dataset-service/s3-kms-key-id
```

### 13.2 How Secrets Reach a Pod

```
Pod startup:
  1. Pod has IRSA role → allowed GetSecretValue for /midas/{service}/*
  2. SecretsManagerAdapter.get("/midas/identity/jwt-signing-key")
     → boto3 call (AWS only) or KeyVault call (Azure) via SecretsPort
  3. Value cached in-process (LRU, 15-min TTL) — never written to disk or env var
  4. On TTL expiry → refreshed from Secrets Manager (supports rotation)
```

### 13.3 Developer Local Setup

```bash
# Local development uses a .env file (git-ignored) with dummy test values
# OR uses AWS SSO + real Secrets Manager via VPN/SSM tunnel
export MIDAS_SECRETS_PROVIDER=env            # use .env instead of Secrets Manager
export MIDAS_AUTH_JWT_SIGNING_KEY=dev-only   # only valid for local dev
```

---

## 17. Caching Strategy (ElastiCache Redis)

Redis is used for four distinct purposes. Each has a dedicated key prefix and TTL.

| Key Pattern | Purpose | TTL | Owner Service |
|---|---|---|---|
| `session:{session_id}` | Auth session token → user context | 1 hour | `identity-service` |
| `authz:{user_id}:{resource_type}:{resource_id}` | Fine-grained permission check result | 5 min | `authz-service` |
| `authz:{user_id}:global` | Global (unscoped) permissions for user | 5 min | `authz-service` |
| `df:{dataset_id}:{scope}` | Compressed parquet DataFrame bytes | 30 min | `dataset-service` |
| `llm-sel:{session_id}` | User LLM model override selection | 8 hours | `llm-service` |
| `rl:{bucket}:{subject}:{window}` | Rate limit counters (Lua atomic) | Window duration | Middleware |
| `train:progress:{job_id}` | Pub/Sub channel for training SSE | Auto-expires on channel inactivity | `computation-service` |
| `qc:{dataset_id}:{analysis}:{hash}` | QC/DQS result cache | 2 hours | `analytics-service` |
| `agent:active:{session_id}` | Active AgentCore session metadata (runtime_id, agent_id, started_at) | 8 hours (session max) | `agent-platform-service` |
| `agent:progress:{run_id}` | Pub/Sub channel for agent step events (tool_name, status, partial_output) | Auto-expires on channel close | `agent-platform-service` |

**Redis key expiry and eviction:**
- Eviction policy: `allkeys-lru` (ElastiCache default for caches)
- Cluster mode: enabled (sharded across 3 nodes for availability)
- Keyspace notifications: enabled for `training:progress:*` pub/sub

---

## 18. State Migration Guide

This section maps each current in-memory or on-disk state artifact to its future home.

| Current State Artifact | Location Today | Future Location | Service Responsible |
|---|---|---|---|
| `DataFrameStateManager._processed_dataframes` | Process RAM | S3 Files parquet + Redis LZ4 bytes | `data-fabric-service` |
| `DataFrameStateManager._split_indices` | Process RAM | DynamoDB `midas-data-catalogue` split items | `data-fabric-service` |
| `split_configs_state.json` | Local disk | DynamoDB `midas-data-catalogue` | `data-fabric-service` |
| `training_jobs_state.json` | Local disk | DynamoDB `midas-pipeline-runs` | `computation-service` |
| Direct `boto3.client('s3')` uploads in `dataset_service.py` | Scattered S3 calls | `data-fabric-service.RegisterArtefact()` gRPC | `data-fabric-service` |
| `message_states` Postgres table (pickled DataFrames) | Postgres blob | DataFrames → S3; metadata → DynamoDB `midas-messages` | `llm-service` |
| `message_states` Postgres table (JSON artefacts) | Postgres JSON | DynamoDB `midas-messages` + artefacts → S3 | `llm-service` |
| `_session_selections` dict in `llm_selection.py` | Process RAM | Redis `llm-sel:{session_id}` | `llm-service` |
| `BackgroundJobManager._jobs` | Process RAM threads | SQS + DynamoDB + KEDA workers | `training-orchestrator` / `training-worker` |
| `vector_store documents.pkl` | Local disk | Amazon OpenSearch Serverless | `graphrag-service` |
| `kg_cache/` directories | Local disk | S3 `midas-knowledge-graphs/` | `graphrag-service` |
| Redis sessions (already external) | ElastiCache | ElastiCache (no change, already correct) | `identity-service` |
| Postgres `users` table + refresh tokens | Postgres | DynamoDB `midas-users` | `identity-service` |
| Legacy bcrypt passwords (`ENABLE_LEGACY_PASSWORD_LOGIN`) | Postgres + code | Removed — Cognito is the IdP | `identity-service` |
| Implicit `if user.role == "admin"` permission checks | Scattered in `routes.py` | `authz-service` RBAC + `AuthzClient` | `authz-service` |
| Rate limit counters (already Redis) | ElastiCache | ElastiCache (no change, already correct) | Istio + middleware |

---

## 19. Developer Workflow

### 20.1 Local Development

Each service can be developed and run independently via Docker Compose. The `midas-common` package provides local test adapters:

```bash
# In any service directory
docker compose up              # starts service + LocalStack (S3/DynamoDB/SQS) + Redis

# With real AWS (VPN required)
MIDAS_CLOUD_PROVIDER=aws \
MIDAS_AWS_PROFILE=midas-dev \
uvicorn main:app --reload
```

`LocalStack` provides AWS-compatible endpoints locally. The factory selects `LocalStackS3StorageAdapter` when `AWS_ENDPOINT_URL=http://localhost:4566` is set.

### 20.2 Adding a New Service

1. Copy the service scaffold from `services/_template/`.
2. Import ports from `midas.factory` only — never `boto3` directly.
3. Define the service's gRPC contract in `midas-common/midas/proto/{service-name}/service.proto`.
4. Run `make proto-gen` in `midas-common` to regenerate Python stubs — commit the generated files.
5. Define a `Dockerfile` (Python 3.12, `midas-common` installed from internal PyPI).
6. Expose both ports in `Dockerfile`: `8080` (REST) and `50051` (gRPC).
7. Add Kubernetes manifests under `deploy/helm/charts/{service-name}/` — include a `Service` with both ports labelled `http` and `grpc`.
8. Add IRSA policy in `deploy/ecs-app/modules/iam/` (Terraform).
9. Register service DNS in Istio `VirtualService` and `AuthorizationPolicy`.

### 20.3 Adding a New Inter-Service Call

1. Add the RPC to the provider service's `.proto` in `midas-common`.
2. Run `make proto-gen`, commit generated stubs.
3. Add the consumer service to the provider's Istio `AuthorizationPolicy` allowlist.
4. Use the pre-built client from `midas.clients.<service>` — never construct a raw gRPC channel in service code.

### 20.4 Adding a New Pipeline Component

1. Choose DynamoDB if the entity is metadata (<100 KB per item, accessed by key or sparse index).
2. Choose S3 if the entity is binary or >100 KB.
3. Define the `NoSQLPort` table schema in the owning service's `models/` directory.
4. Add the table to the service's Terraform module under `deploy/ecs-app/modules/`.
5. Never share a table between services — other services call the owner's API.

### 20.5 Running the Full Stack Locally

```bash
# Start the full service graph
docker compose -f docker-compose.dev.yml up

# Individual service logs
docker compose logs -f dataset-service

# Test inter-service calls
curl -H "Authorization: Bearer $(make dev-token)" \
  http://localhost:8000/v1/datasets
```

---

## 20. End-to-End Transaction: GBM Model Training

This section traces a complete real-world transaction — a user training a Gradient Boosting Machine model — from the browser through every microservice to the finished artefact. This is the primary reference for developers implementing or refactoring any part of this flow.

**Actors:**
- **User** — a human analyst using the MIDAS web application
- **Web UI** — the React frontend SPA (browser)
- **AWS WAF** — inspects every inbound HTTPS request
- **AWS ALB** — terminates TLS, routes to Istio Ingress Gateway
- **Istio Ingress Gateway** — routes REST requests to the correct service
- **identity-service** — validates session JWT on every request (via Istio `RequestAuthentication`)
- **authz-service** — answers "can this user do this action?" (gRPC, called per protected operation)
- **data-fabric-service** — owns all dataset and artefact storage
- **analytics-service** — runs QC/DQS checks on the dataset before training is allowed
- **computation-service** — Kubeflow facade; creates and manages the training pipeline run
- **Kubeflow Pipelines (Argo Workflows)** — executes step pods in `midas-pipelines` namespace
- **feature-engineer component pod** — runs feature engineering as a Kubeflow pipeline step
- **gbm-trainer component pod** — trains the GBM model as a Kubeflow pipeline step
- **meea-evaluator component pod** — computes model evaluation metrics
- **evaluation-service** — persists MEEA results
- **ElastiCache Redis** — hot DataFrame cache
- **AWS S3 / S3 Files** — raw data and processed artefacts
- **DynamoDB** — metadata for all entities

---

### 21.1 Pre-conditions

The user is already logged in. Their browser holds:
- `midas_session` JWT (1-hour access token)
- `midas_rt` httpOnly refresh cookie

A dataset has already been uploaded and split. `dataset_id = "ds-001"` exists in DynamoDB `midas-data-catalogue` and its parquet is in S3 Files.

---

### 21.2 Step-by-Step Transaction Flow

```
═══════════════════════════════════════════════════════════════════════════════
STEP 1 — User selects GBM algorithm and clicks "Run QC then Train"
Actor: User + Web UI
═══════════════════════════════════════════════════════════════════════════════

Web UI builds request:
  POST /api/v1/analytics/qc
  Authorization: Bearer <midas_session_jwt>
  Body: { "dataset_id": "ds-001", "checks": ["missing_values", "distribution", "target_leakage"] }

───────────────────────────────────────────────────────────────────
Web UI → HTTPS → NLB :443
NLB (TCP passthrough) → ALB :443
AWS WAF inspects:
  ✓ OWASP rules pass
  ✓ Authorization header present
  ✓ Rate limit: 18/2000 req
ALB terminates TLS → HTTP :80 → Istio Ingress Gateway NodePort
───────────────────────────────────────────────────────────────────
Istio Ingress Gateway:
  matches VirtualService rule: /api/v1/analytics/* → analytics-service:8080
  Istio RequestAuthentication:
    validates midas_session_jwt signature using JWKS from identity-service
    ✓ valid: sets x-jwt-payload header with {user_id, email, groups}
───────────────────────────────────────────────────────────────────
analytics-service  (REST handler: POST /api/v1/analytics/qc)
  1. Extracts user_id from x-jwt-payload header
  2. gRPC → authz-service:50051
        CheckPermission {
          user_id: "user-123",
          action: "analytics:run-qc",
          resource_type: "dataset",
          resource_id: "ds-001"
        }
        ← { allowed: true, matched_role: "analyst" }
  3. gRPC → data-fabric-service:50051
        GetDataset { dataset_id: "ds-001" }
        ← { dataset_id, project_id, name, latest_version, schema }
  4. gRPC → data-fabric-service:50051
        GetDataframe { dataset_id: "ds-001", scope: "full", version: "latest" }
        ← DataframeBytes { parquet_lz4: <bytes>, row_count: 50000, col_count: 42 }
        (data-fabric-service checks Redis df:ds-001:full → hit → returns cached bytes)
  5. Reconstructs pd.DataFrame from parquet bytes (local to this request)
  6. Runs QC checks: missing_values, distribution skew, target leakage detection
  7. Writes QC results:
        NoSQLPort.put(DynamoDB "midas-analytics-results",
          PK: "ds-001", SK: "qc#run-001",
          result: {missing: 0.2%, skew: ok, leakage: none})
  8. Returns:
        ← 200 { qc_run_id: "run-001", status: "passed", issues: [], warnings: [{...}] }

Web UI renders QC results panel.
User reviews — no blocking issues — clicks "Proceed to Train".

═══════════════════════════════════════════════════════════════════════════════
STEP 2 — User configures GBM hyperparameters and submits training
Actor: User + Web UI
═══════════════════════════════════════════════════════════════════════════════

Web UI builds request:
  POST /api/v1/computation/pipelines/gbm-standard-v2/runs
  Authorization: Bearer <midas_session_jwt>
  Body: {
    "dataset_id": "ds-001",
    "split_id": "split-001",
    "qc_run_id": "run-001",
    "hyperparams": {
      "algorithm": "lightgbm",
      "n_estimators": 500,
      "max_depth": 6,
      "learning_rate": 0.05,
      "target_column": "churn"
    },
    "pipeline_id": "gbm-standard-v2"
  }

───────────────────────────────────────────────────────────────────
WAF → ALB → Istio Gateway
VirtualService: /api/v1/computation/* → computation-service:8080
Istio validates JWT → sets x-jwt-payload
───────────────────────────────────────────────────────────────────
computation-service  (REST handler: POST /api/v1/computation/pipelines/{id}/runs)
  1. Extracts user_id from x-jwt-payload
  2. gRPC → authz-service:50051
        CheckPermission { user_id, action: "computation:run-pipeline",
                          resource_type: "pipeline", resource_id: "gbm-standard-v2" }
        ← { allowed: true }
  3. Validates qc_run_id exists and status == "passed":
        NoSQLPort.get(DynamoDB "midas-analytics-results", PK: "ds-001", SK: "qc#run-001")
        ← { status: "passed" }  ✓
  4. gRPC → data-fabric-service:50051
        GetDataset { dataset_id: "ds-001" }
        ← validates dataset exists and split "split-001" exists
  5. Creates run record:
        NoSQLPort.put(DynamoDB "midas-pipeline-runs",
          run_id: "run-002",
          pipeline_id: "gbm-standard-v2",
          dataset_id: "ds-001",
          user_id: "user-123",
          status: "SUBMITTED",
          created_at: now)
  6. Fetches pipeline definition:
        NoSQLPort.get(DynamoDB "midas-pipeline-catalogue", PK: "PIPELINE#gbm-standard-v2")
        ← { steps: [feature-engineer-v2, gbm-trainer-v3, meea-evaluator-v1], dag: {...} }
  7. Compiles KFP pipeline YAML from definition + params
  8. Submits to Kubeflow API server:
        kubeflow_sdk.create_run(
          pipeline_yaml=compiled_yaml,
          params={dataset_id, split_id, hyperparams},
          run_name="run-002"
        )
        ← { kfp_run_id: "kfp-run-abc123" }
  9. Updates DynamoDB:
        NoSQLPort.update("midas-pipeline-runs", run_id: "run-002",
          status: "RUNNING", kfp_run_id: "kfp-run-abc123")
  10. Returns immediately:
        ← 202 Accepted { run_id: "run-002", status: "RUNNING" }

Web UI starts polling SSE stream.

═══════════════════════════════════════════════════════════════════════════════
STEP 3 — Web UI opens SSE progress stream
Actor: Web UI
═══════════════════════════════════════════════════════════════════════════════

Web UI:
  GET /api/v1/computation/runs/run-002/stream
  Accept: text/event-stream
  Authorization: Bearer <midas_session_jwt>

computation-service  (SSE handler)
  Subscribes to Redis pub/sub channel: "train:progress:run-002"
  Streams events to browser as they arrive.
  Browser renders live step progress: "▸ feature-engineer — running..."

═══════════════════════════════════════════════════════════════════════════════
STEP 4 — Kubeflow schedules pipeline step pods
Actor: Kubeflow Pipelines (Argo Workflows controller)
═══════════════════════════════════════════════════════════════════════════════

Kubeflow Argo Workflow controller (kubeflow namespace):
  Reads KFP run "kfp-run-abc123"
  Schedules step pods in midas-pipelines namespace per DAG order:
    Step 1: feature-engineer-v2 pod (ECR image: midas/feature-engineer:v2)
    Step 2: gbm-trainer-v3 pod      (depends on step 1 output)
    Step 3: meea-evaluator-v1 pod   (depends on step 2 output)

═══════════════════════════════════════════════════════════════════════════════
STEP 5 — Feature Engineering step pod executes
Actor: feature-engineer-v2 pod (Kubeflow pipeline step)
Namespace: midas-pipelines
ServiceAccount: pipeline-step-sa (IRSA: read data-fabric gRPC, write S3 Files)
═══════════════════════════════════════════════════════════════════════════════

feature-engineer-v2 pod starts:
  1. gRPC → data-fabric-service.midas-services.svc.cluster.local:50051
        GetDataframe { dataset_id: "ds-001", scope: "full", version: "latest" }
        data-fabric-service checks Redis "df:ds-001:full:v1" → hit
        ← DataframeBytes { parquet_lz4: <50k rows × 42 cols compressed bytes> }
  2. Reconstructs pd.DataFrame (50,000 rows × 42 columns) in pod memory
  3. Runs feature engineering:
        - encode categorical columns
        - impute missing values (median strategy)
        - log-transform skewed numerics
        - generate interaction features
        output_df: 50,000 rows × 67 columns (engineered)
  4. Serialises output to parquet bytes (LZ4 compressed)
  5. gRPC → data-fabric-service:50051
        RegisterArtefact {
          job_id: "run-002",
          artefact_type: "feature-eng-output",
          parquet_bytes: <bytes>,
          metadata: { input_cols: 42, output_cols: 67 }
        }
        data-fabric-service:
          StoragePort.put(S3 Files "midas-artefacts/run-002/feature-eng/output.parquet")
          NoSQLPort.put(DynamoDB "midas-data-catalogue",
            PK: "ARTEFACT#run-002", SK: "TYPE#feature-eng-output",
            s3_files_key: "midas-artefacts/run-002/feature-eng/output.parquet")
          CachePort.set(Redis "df:run-002:feature-eng:v1", parquet_bytes, ttl=3600)
        ← { artefact_ref: "artefact-fe-001" }
  6. Publishes progress to Redis:
        redis.publish("train:progress:run-002",
          '{"step":"feature-engineer","status":"COMPLETE","output_cols":67}')
        → computation-service SSE handler forwards to browser
  7. Pod exits cleanly. Argo marks step 1 COMPLETE.

═══════════════════════════════════════════════════════════════════════════════
STEP 6 — GBM Training step pod executes
Actor: gbm-trainer-v3 pod (Kubeflow pipeline step)
Namespace: midas-pipelines
═══════════════════════════════════════════════════════════════════════════════

gbm-trainer-v3 pod starts (after feature-eng step COMPLETE):
  1. gRPC → data-fabric-service:50051
        GetDataframe { dataset_id: "ds-001", scope: "train", version: "latest" }
        data-fabric-service: Redis miss → S3 Files read
        StoragePort.get("midas-datasets/parquet/ds-001/latest/train.parquet")
        CachePort.set(Redis "df:ds-001:train:v1", ..., ttl=1800)
        ← DataframeBytes { 40,000 rows × 42 cols }
  2. gRPC → data-fabric-service:50051
        GetArtefact { artefact_ref: "artefact-fe-001" }    ← feature-eng output
        ← FileBytes { parquet bytes for 40,000 rows × 67 engineered columns }
  3. Reconstructs train DataFrame + engineered features
  4. Trains LightGBM model:
        lgbm.LGBMClassifier(
          n_estimators=500, max_depth=6, learning_rate=0.05
        ).fit(X_train_engineered, y_train)
        [~120 seconds of CPU computation]
  5. Serialises model:
        joblib.dump(model, "/tmp/gbm_model.pkl")
  6. gRPC → data-fabric-service:50051
        RegisterArtefact {
          job_id: "run-002",
          artefact_type: "model-pkl",
          file_bytes: <model pickle bytes>,
          metadata: {
            algorithm: "lightgbm",
            n_estimators: 500,
            feature_names: [67 column names],
            train_rows: 40000,
            train_auc: 0.847
          }
        }
        data-fabric-service:
          StoragePort.put(S3 Files "midas-artefacts/run-002/model/gbm_model.pkl")
          NoSQLPort.put(DynamoDB "midas-data-catalogue",
            PK: "ARTEFACT#run-002", SK: "TYPE#model-pkl",
            s3_files_key: "...", metadata: {...})
        ← { artefact_ref: "artefact-model-001" }
  7. Publishes progress:
        redis.publish("train:progress:run-002",
          '{"step":"gbm-trainer","status":"COMPLETE","train_auc":0.847}')
  8. Pod exits. Argo marks step 2 COMPLETE.

═══════════════════════════════════════════════════════════════════════════════
STEP 7 — MEEA Evaluation step pod executes
Actor: meea-evaluator-v1 pod
Namespace: midas-pipelines
═══════════════════════════════════════════════════════════════════════════════

meea-evaluator-v1 pod starts:
  1. gRPC → data-fabric-service:50051
        GetDataframe { dataset_id: "ds-001", scope: "test" }
        ← DataframeBytes { 10,000 rows (test set) }
  2. gRPC → data-fabric-service:50051
        GetArtefact { artefact_ref: "artefact-model-001" }
        ← FileBytes { gbm_model.pkl }
  3. Reconstructs test DataFrame and loads model
  4. Runs evaluation:
        y_pred = model.predict_proba(X_test_engineered)
        metrics = {
          auc_roc: 0.831,
          auc_pr: 0.764,
          f1: 0.712,
          confusion_matrix: [[8102,398],[901,599]],
          feature_importance: {col1: 0.12, col2: 0.09, ...}
        }
  5. gRPC → evaluation-service.midas-services.svc.cluster.local:50051
        StoreEvaluation {
          model_id: "run-002",
          eval_type: "meea",
          metrics: metrics,
          artefact_ref: "artefact-model-001"
        }
        evaluation-service:
          NoSQLPort.put(DynamoDB "midas-evaluations", PK: "run-002", SK: "meea")
          StoragePort.put(S3 Files "midas-artefacts/run-002/eval/meea.json.gz")
        ← { eval_ref: "eval-001" }
  6. gRPC → data-fabric-service:50051
        RegisterArtefact {
          artefact_type: "evaluation",
          file_ref: "eval-001",
          metadata: { auc_roc: 0.831, f1: 0.712 }
        }
  7. Publishes final progress:
        redis.publish("train:progress:run-002",
          '{"step":"meea-evaluator","status":"COMPLETE","auc_roc":0.831}')
  8. Pod exits. Argo marks step 3 COMPLETE. KFP pipeline run → SUCCEEDED.

═══════════════════════════════════════════════════════════════════════════════
STEP 8 — computation-service detects completion
Actor: computation-service (background poller / KFP webhook)
═══════════════════════════════════════════════════════════════════════════════

computation-service KFP watcher detects run "kfp-run-abc123" → SUCCEEDED:
  NoSQLPort.update(DynamoDB "midas-pipeline-runs", run_id: "run-002",
    status: "COMPLETE",
    artefacts: ["artefact-fe-001", "artefact-model-001", "eval-001"],
    completed_at: now,
    metrics: { auc_roc: 0.831, f1: 0.712 })

redis.publish("train:progress:run-002",
  '{"status":"COMPLETE","auc_roc":0.831,"f1":0.712,"run_id":"run-002"}')

computation-service SSE handler → browser receives final event:
  data: {"status":"COMPLETE","auc_roc":0.831,"f1":0.712}

SSE stream closes.

═══════════════════════════════════════════════════════════════════════════════
STEP 9 — Web UI polls final status and renders results
Actor: Web UI
═══════════════════════════════════════════════════════════════════════════════

Web UI:
  GET /api/v1/computation/runs/run-002
  Authorization: Bearer <midas_session_jwt>

WAF → ALB → Istio → computation-service:
  NoSQLPort.get(DynamoDB "midas-pipeline-runs", run_id: "run-002")
  ← 200 {
      run_id: "run-002",
      status: "COMPLETE",
      pipeline_id: "gbm-standard-v2",
      artefacts: [
        { type: "model-pkl", ref: "artefact-model-001" },
        { type: "evaluation", ref: "eval-001" }
      ],
      metrics: { auc_roc: 0.831, f1: 0.712 }
    }

Web UI renders: model scorecard, feature importance chart, confusion matrix.
User clicks "Download Model Report".

Web UI:
  GET /api/v1/evaluation/run-002
  ← 200 { auc_roc: 0.831, auc_pr: 0.764, confusion_matrix: [...], feature_importance: {...} }

═══════════════════════════════════════════════════════════════════════════════
COMPLETE TRANSACTION SUMMARY
═══════════════════════════════════════════════════════════════════════════════
```

---

### 21.3 Component Interaction Map (GBM Training)

```
Actor        HTTP/REST call                Service          gRPC call              Dependency
────────────────────────────────────────────────────────────────────────────────────────────
User/Web UI  POST /api/v1/analytics/qc ──► analytics-svc ──gRPC──► authz-svc
                                                          ──gRPC──► data-fabric-svc
                                                          ──write──► DynamoDB (results)

User/Web UI  POST /api/v1/computation/    computation-svc ──gRPC──► authz-svc
             pipelines/{id}/runs       ──►                ──gRPC──► data-fabric-svc
                                                          ──NoSQL──► DynamoDB (runs)
                                                          ──SDK───► Kubeflow API server

Web UI       GET /api/v1/computation/  ──► computation-svc ──pubsub► Redis ──► SSE stream
             runs/{id}/stream

[Kubeflow]   schedules pods            ──► feature-eng pod ──gRPC──► data-fabric-svc (get)
                                                            ──gRPC──► data-fabric-svc (register)
                                                            ──pub───► Redis (progress)

[Kubeflow]   schedules pods            ──► gbm-trainer pod ──gRPC──► data-fabric-svc (get ×2)
                                                            ──gRPC──► data-fabric-svc (register)
                                                            ──pub───► Redis (progress)

[Kubeflow]   schedules pods            ──► meea-eval pod   ──gRPC──► data-fabric-svc (get ×2)
                                                            ──gRPC──► evaluation-svc
                                                            ──gRPC──► data-fabric-svc (register)
                                                            ──pub───► Redis (progress)

[KFP watcher] detects COMPLETE         ──► computation-svc ──NoSQL──► DynamoDB (update run)
                                                            ──pub───► Redis (final event)

User/Web UI  GET /api/v1/computation/  ──► computation-svc ──NoSQL──► DynamoDB (get run)
             runs/{id}

User/Web UI  GET /api/v1/evaluation/   ──► evaluation-svc  ──NoSQL──► DynamoDB (get meea)
             {run_id}
```

---

### 21.4 New Code Required for this Flow

This table tells every developer exactly which file they need to create or refactor for this specific transaction.

| File | Service | New / Refactor | What it replaces / what it does |
|---|---|---|---|
| `analytics-service/app/api/analytics_routes.py` | `analytics-service` | **New** | Extracts `/qc`, `/dqs`, `/correlations` from monolith `routes.py` |
| `analytics-service/app/services/qc_service.py` | `analytics-service` | Refactor | Wraps `data_quality_detector.py` logic; calls `DataFabricClient.GetDataframe()` instead of `DataFrameStateManager` |
| `data-fabric-service/app/grpc/data_fabric_servicer.py` | `data-fabric-service` | **New** | Implements `GetDataframe`, `RegisterArtefact`, `GetArtefact` RPCs |
| `data-fabric-service/app/services/catalogue_service.py` | `data-fabric-service` | **New** | DynamoDB single-table design for `midas-data-catalogue` |
| `computation-service/app/api/run_routes.py` | `computation-service` | **New** | Extracts `/train`, `/auto-train` from `routes.py`; calls Kubeflow SDK |
| `computation-service/app/services/kubeflow_service.py` | `computation-service` | **New** | Wraps `kfp.Client` SDK; compiles + submits pipeline runs |
| `pipeline-components/gbm_trainer/component.py` | pipeline component | Refactor | Extracts `model_training.py` LightGBM/CatBoost/XGBoost logic; calls `DataFabricClient` instead of `DataFrameStateManager` |
| `pipeline-components/feature_engineer/component.py` | pipeline component | Refactor | Extracts `feature_engineering_service.py`; calls `DataFabricClient` |
| `pipeline-components/meea_evaluator/component.py` | pipeline component | Refactor | Extracts `model_evaluation_service.py`; calls `EvaluationServiceClient` gRPC |
| `evaluation-service/app/grpc/evaluation_servicer.py` | `evaluation-service` | **New** | Implements `StoreEvaluation` RPC; writes to DynamoDB `midas-evaluations` |
| `midas-common/midas/clients/data_fabric.py` | `midas-common` | **New** | Pre-built `DataFabricClient` (gRPC stub wrapper); used by all step pods and services |
| `midas-common/midas/clients/authz.py` | `midas-common` | **New** | `AuthzClient` gRPC wrapper; used by every REST handler |
| `midas-common/midas/proto/data_fabric/data_fabric.proto` | `midas-common` | **New** | Defines `GetDataframe`, `RegisterArtefact`, `GetArtefact`, `GetLineage` RPCs |
| `midas-common/midas/proto/computation/computation.proto` | `midas-common` | **New** | Defines `SubmitRun`, `GetRunStatus` RPCs |

---

## 21. Requirements Validation

This section maps every requirement stated during architecture sessions to where it is addressed in this document.

| Requirement | Where addressed | Status |
|---|---|---|
| 100% microservice architecture | §4, §5 — 14 independent services | ✓ |
| AWS EKS as container platform | §12 — EKS cluster, namespaces, pod templates | ✓ |
| Kubernetes pods and services | §12.1–12.4 — namespaces, IRSA, pod spec | ✓ |
| Istio service mesh | §12.4 — PeerAuthentication, VirtualService, DestinationRule | ✓ |
| gRPC for service-to-service | §13.1 — all internal calls use gRPC; proto files in §8.3, §7.4 | ✓ |
| REST for external API boundary | §13.2 — all external endpoints documented per service | ✓ |
| AWS Cognito for authentication | §6.2 — PKCE flow, session JWT, identity-service | ✓ |
| Dedicated auth service (identity-service) | §5.1, §6 deep-dive | ✓ |
| Dedicated authorisation + RBAC service (authz-service) | §5.2, §6 deep-dive, RBAC model | ✓ |
| data-fabric-service (data-centric service) | §5.4, §7 deep-dive, DynamoDB catalogue, S3 Files layout | ✓ |
| AWS S3 Files for data sharing between services | §7.2 — S3 Files for parquet, artefacts; §10.2 — bucket layout | ✓ |
| DynamoDB over SQLite/Postgres where possible | §10.1 — all tables defined; §17 — migration guide | ✓ |
| ElastiCache Redis as caching layer | §16 — all Redis key patterns and TTLs | ✓ |
| AWS Secrets Manager for secrets | §15 — naming convention, pod startup fetch, rotation | ✓ |
| Computation service on Kubeflow | §5.7, §8 deep-dive, pipeline components, Argo Workflows | ✓ |
| Pipeline catalogue (create/edit/delete/metadata) | §8.3 — full CRUD API for pipelines, components, functions | ✓ |
| Pipeline components (reusable, versioned) | §8.2 — Component concept, DynamoDB storage, KFP SDK | ✓ |
| AWS ALB for web application ingress | §9.1 — NLB→WAF→ALB→Istio traffic flow | ✓ |
| AWS WAF on the ALB | §9.2–9.3 — WAF rules, logging, security group flow | ✓ |
| Cloud portability abstraction (AWS/Azure/GCP) | §11 — Port interfaces, adapters, factory; §14 — portability table | ✓ |
| DynamoDB abstraction for portability | §14 portability note — NoSQLPort hides DynamoDB API | ✓ |
| Developer code structure (what to write) | §4.2 — full service repo structure; §19.4 — per-flow file table | ✓ |
| End-to-end transaction flow (GBM training) | §19 — every actor, API call, gRPC call, data store | ✓ |
| Code separation into microservices (what moves where) | §4.1 — monolith file → service mapping table | ✓ |
| Current code that needs refactoring | §4.1 (Refactor column), §18 state migration guide | ✓ |
| AI Agent Fabric (`agent-platform-service`) | §5.11, §10 deep-dive — AgentCore abstraction | ✓ |
| AWS AgentCore for agent runtime | §10.2 — `AgentCoreAdapter`, `AgentRuntimePort`, `agentcore_service.py` | ✓ |
| Agent session management (isolated microVM, up to 8h) | §10.4 — session lifecycle, session_id strategy, terminate on idle | ✓ |
| Agent long-term memory across sessions | §10.5 — AgentCore Memory API, `store_memory` / `retrieve_memory` | ✓ |
| MIDAS platform capabilities as Agent Tools (MCP) | §10.3 — 24 tools covering every MIDAS service | ✓ |
| RBAC enforced for agent tool calls | §10.3 — `authz_tool.py` CheckPermission gate in every tool adapter | ✓ |
| Out-of-the-box agents | §10.6 — 5 OOB agents seeded in `midas-agent-catalogue` DynamoDB | ✓ |
| User-defined custom agents | §5.11 `POST /api/v1/agents` + §10 tool registry | ✓ |
| AI Agent Fabric cloud portability | §10.2 — `AgentRuntimePort` interface; Azure Foundry adapter swap | ✓ |
| Agents access platform via REST/gRPC (same as human users) | §10.3 — every tool calls the owning service's existing gRPC or REST API | ✓ |
| AI agent workloads run on EKS cluster | §10.1 — `midas-agents` namespace; AgentCore microVM within EKS | ✓ |
| Agent runs stored and auditable | §10.7 — `midas-agent-runs` DynamoDB with tool_calls[], output, timestamps | ✓ |

---

## 22. Architecture Diagrams

### 22.1 High-Level Future State

```
                              ┌─────────────────────────────────────────────┐
                              │              AWS VPC (10.72.134.0/23)        │
                              │                                             │
  Internal Client ────────►  │  Corporate DNS → NLB → WAF → ALB            │
                              │       │                                     │
                              │       ▼                                     │
                              │  ┌──────────────────────────────────────┐  │
                              │  │        EKS Cluster: midas-eks         │  │
                              │  │                                       │  │
                              │  │  Istio Ingress Gateway               │  │
                              │  │       │                               │  │
                              │  │  ┌────┴───────────────────────────┐  │  │
                              │  │  │   midas-services namespace      │  │  │
                              │  │  │                                 │  │  │
                              │  │  │  identity  authz  project       │  │  │
                              │  │  │  data-fabric  analytics  llm    │  │  │
                              │  │  │  computation  graphrag  eval    │  │  │
                              │  │  │  documentation-service          │  │  │
                              │  │  │  agent-platform-service  ← NEW  │  │  │
                              │  │  └────────────────────────────────┘  │  │
                              │  │  ┌────────────────────────────────┐  │  │
                              │  │  │   kubeflow + midas-pipelines   │  │  │
                              │  │  │   Argo step pods (ephemeral)   │  │  │
                              │  │  └────────────────────────────────┘  │  │
                              │  │  ┌────────────────────────────────┐  │  │
                              │  │  │   midas-agents namespace       │  │  │
                              │  │  │   AgentCore microVM sessions   │  │  │
                              │  │  │   (isolated per conversation)  │  │  │
                              │  │  └────────────────────────────────┘  │  │
                              │  └──────────────────────────────────────┘  │
                              │                                             │
                              │  ┌──────────────────────────────────────┐  │
                              │  │          Managed Services             │  │
                              │  │                                       │  │
                              │  │  DynamoDB ──── ElastiCache Redis     │  │
                              │  │  S3 + S3 Files ─ Secrets Manager     │  │
                              │  │  OpenSearch ── AI Gateway (LiteLLM)  │  │
                              │  │  Cognito User Pool (PrivateLink)     │  │
                              │  │  AgentCore Runtime (PrivateLink)     │  │
                              │  │  AgentCore Memory  (PrivateLink)     │  │
                              │  └──────────────────────────────────────┘  │
                              │                                             │
                              │  Transit Gateway → Corporate Network        │
                              └─────────────────────────────────────────────┘
```

### 22.2 Request Flow: Data Upload (Summary)

```
1. POST /api/v1/data/upload
   Client ──► NLB → WAF (inspect) → ALB → Istio Gateway ──► data-fabric-service
                                                                   │
                                                          StoragePort.put(S3 raw)
                                                          StoragePort.put(S3 Files parquet)
                                                          NoSQLPort.put(DynamoDB midas-data-catalogue)
                                                          CachePort.set(Redis df:{id}:full)
                                                                   │
                                                          ◄── 201 {dataset_id}

2. POST /api/v1/computation/pipelines/{id}/runs  {dataset_id, hyperparams}
   Client ──► computation-service
                   │
          NoSQLPort.put(DynamoDB midas-pipeline-runs, status=PENDING)
          Kubeflow SDK.submit_pipeline_run(pipeline_id, params)
                   │
          ◄── 202 {run_id}

3. Kubeflow Argo Workflow (step pods in midas-pipelines ns)
   feature-eng-step-pod
        │
        gRPC → data-fabric-service.GetDataframe(dataset_id, "full")
        │      → CachePort hit (Redis) or S3 Files read
        │
        run feature engineering
        │
        gRPC → data-fabric-service.RegisterArtefact(run_id, s3_key, "feature-eng-output")

   model-train-step-pod
        │
        gRPC → data-fabric-service.GetDataframe(dataset_id, "train")
        │
        run model training (sklearn / catboost / lightgbm)
        │
        gRPC → data-fabric-service.RegisterArtefact(run_id, s3_key, "model-pkl")
        gRPC → evaluation-service.StoreEvaluation(run_id, meea_payload)

4. GET /api/v1/computation/runs/{run_id}/status
   Client ──► computation-service
                   │
          NoSQLPort.get(DynamoDB midas-pipeline-runs)
                   │
          ◄── 200 {status: "COMPLETE", artefacts: [...]}
```

### 22.3 Portability Swap Diagram

```
Application Code (unchanged)
         │
         │  imports
         ▼
  midas.factory.get_storage()
         │
         │  reads MIDAS_CLOUD_PROVIDER
         │
    ┌────┴──────────┬────────────────┐
    ▼               ▼                ▼
 "aws"          "azure"           "gcp"
    │               │                │
S3StorageAdapter  BlobStorageAdapter  GCSStorageAdapter
(boto3/S3 Files)  (azure-storage-blob)  (google-cloud-storage)
```

---

## Appendix A: Mapping of Removed Anti-Patterns

| Anti-pattern (current) | Why removed | Replacement |
|---|---|---|
| `DataFrameStateManager` singleton | Breaks horizontal scale; pod-local | S3 + Redis DataFrame cache |
| `BackgroundJobManager` threads | No distributed visibility, dies with pod | Kubeflow Pipelines + Argo Workflow step pods |
| `training_jobs_state.json` | Pod-local file, lost on restart | DynamoDB `midas-pipeline-runs` |
| SQS `midas-training-queue` + KEDA worker | Queue-based fan-out replaced by DAG-based pipeline platform | Kubeflow Pipelines (Argo Workflows) |
| Direct `boto3.client('s3')` calls scattered across services | Locks to AWS; no single data owner | `data-fabric-service` gRPC API + `StoragePort` abstraction |
| `split_configs_state.json` | Pod-local file | DynamoDB `midas-datasets` |
| `SQLite` fallback | Can't share across pods | DynamoDB (all envs) |
| Pickled DataFrames in `message_states` Postgres table | ~50 MiB blobs in RDBMS | S3 parquet + DynamoDB metadata |
| `SECRET_KEY = "your-secret-key"` in `auth_service.py` | Secret in code | Secrets Manager via `SecretsPort` in `identity-service` |
| Implicit route-level permission checks (`if user.role == "admin"`) | Scattered, untestable, no audit trail | Centralised `authz-service` RBAC with `AuthzClient` |
| `graphrag_process_manager` spawning Python subprocesses | Subprocess in container = second process, no lifecycle | Dedicated `graphrag-service` Pod |
| FAISS index on local disk (`documents.pkl`) | Pod-local, not shared | Amazon OpenSearch Serverless |
| LLM selection in process-local dict (`_session_selections`) | Lost on pod restart | Redis `llm-sel:{session_id}` |
| `boto3` direct calls scattered across services | Locks to AWS | `StoragePort`/`NoSQLPort` adapters |

---

## Appendix B: Migration Phasing (Suggested Order)

| Phase | Services / Work | Goal |
|---|---|---|
| **Phase 0** | Introduce `midas-common` portability package; write AWS adapters, `AuthzClient`, proto stubs, and unit tests | Shared foundation; no behaviour change |
| **Phase 1** | Extract `identity-service` (Cognito, JWT, sessions, user provisioning) | Cleanest boundary; no downstream deps |
| **Phase 2** | Extract `authz-service` (RBAC tables, gRPC `CheckPermission`, Redis cache); update all services to use `AuthzClient` | Centralise permissions before other services diverge |
| **Phase 3** | Extract `project-service` | Low coupling; depends only on identity + authz |
| **Phase 4** | Extract `data-fabric-service`; migrate DataFrames to S3 Files + Redis; build `midas-data-catalogue` DynamoDB table | Remove the #1 scaling blocker; establish single data owner |
| **Phase 5** | Extract `analytics-service`; point at `data-fabric-service` gRPC | Stateless compute — easiest after data-fabric |
| **Phase 6** | Extract `llm-service`; migrate `message_states` to DynamoDB; Redis for LLM selection | Clears second major state blocker |
| **Phase 7** | Deploy **Kubeflow Pipelines** on EKS (`kubeflow` namespace + `midas-pipelines` namespace); extract `computation-service`; migrate training logic to Kubeflow components; replace SQS+KEDA pattern | Core ML platform shift; eliminates `BackgroundJobManager` and all thread-based training |
| **Phase 8** | Extract `graphrag-service` (already HTTP-adjacent); migrate FAISS → OpenSearch | Most isolated |
| **Phase 9** | Attach **AWS WAF** to ALB; add WAF rules, logging to S3; configure Istio VirtualService routing | Harden web application ingress |
| **Phase 10** | Extract `documentation-service`; `evaluation-service` | Lowest risk, late-phase cleanup |
| **Phase 11** | Remove SQLite codepaths; retire `_db_backend.py`; full DynamoDB; remove SQS `midas-training-queue` | Final state |

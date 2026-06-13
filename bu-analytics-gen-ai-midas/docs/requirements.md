# MIDAS — Solution Requirements

**Document:** `docs/requirements.md`  
**Status:** Living document — updated as requirements are agreed  
**Audience:** Software developers, architects, product owners  
**Date:** 2026-04-28

---

## Table of Contents

1. [Platform Architecture Requirements](#1-platform-architecture-requirements)
2. [Infrastructure Requirements](#2-infrastructure-requirements)
3. [Microservice Requirements](#3-microservice-requirements)
4. [Authentication & Authorisation Requirements](#4-authentication--authorisation-requirements)
5. [Data Management Requirements](#5-data-management-requirements)
6. [Computation & ML Pipeline Requirements](#6-computation--ml-pipeline-requirements)
7. [AI Agent Fabric Requirements](#7-ai-agent-fabric-requirements)
8. [Ingress & Web Application Requirements](#8-ingress--web-application-requirements)
9. [Communication Protocol Requirements](#9-communication-protocol-requirements)
10. [Cloud Portability Requirements](#10-cloud-portability-requirements)
11. [Security Requirements](#11-security-requirements)
12. [Caching Requirements](#12-caching-requirements)
13. [Observability Requirements](#13-observability-requirements)
14. [Developer Experience Requirements](#14-developer-experience-requirements)
15. [Diagram & Documentation Requirements](#15-diagram--documentation-requirements)

---

## 1. Platform Architecture Requirements

| ID | Requirement | Status |
|---|---|---|
| ARCH-001 | The backend shall be a 100% microservice architecture. No monolithic FastAPI application in the future state. | ✅ Agreed |
| ARCH-002 | All microservices shall run as Kubernetes Pods on AWS EKS in region `us-east-1`. | ✅ Agreed |
| ARCH-003 | All services shall be stateless at the pod level. No pod holds durable in-process state. | ✅ Agreed |
| ARCH-004 | Durable state shall persist exclusively to managed stores: DynamoDB, ElastiCache Redis, S3, or AWS S3 Files. | ✅ Agreed |
| ARCH-005 | All services shall share a common `midas-common` pip package providing portability abstractions, gRPC client stubs, and middleware. | ✅ Agreed |
| ARCH-006 | The architecture shall have two central platform layers — **Data Fabric** and **Computation Fabric** — with a Service Mesh as a cross-cutting layer. All other microservices orbit these central layers. | ✅ Agreed |
| ARCH-007 | The solution shall run entirely within VPC `vpc-0c4d673f3e95a93eb` (CIDR `10.72.134.0/23`). No public endpoints, no public IPs, no Internet Gateways, no NAT Gateways. | ✅ Agreed |

---

## 2. Infrastructure Requirements

| ID | Requirement | Status |
|---|---|---|
| INFRA-001 | All workloads shall run on AWS EKS in a single region (`us-east-1`). No multi-region. | ✅ Agreed |
| INFRA-002 | An Istio service mesh shall be deployed across all pod namespaces. All pod-to-pod traffic shall be mTLS STRICT. | ✅ Agreed |
| INFRA-003 | All AWS API calls (DynamoDB, S3, Secrets Manager, Bedrock AgentCore) shall use VPC Interface Endpoints (PrivateLink) with private DNS. | ✅ Agreed |
| INFRA-004 | Egress from the VPC shall use Transit Gateway `tgw-0ec391fa73943d562`. No NAT Gateway. | ✅ Agreed |
| INFRA-005 | Each service shall have its own Kubernetes namespace (`midas-services`, `midas-agents`, `midas-pipelines`, `kubeflow`). | ✅ Agreed |
| INFRA-006 | Service accounts shall use IRSA (IAM Roles for Service Accounts). No static AWS credentials in pods. | ✅ Agreed |
| INFRA-007 | Deployments shall be managed by Helm charts, triggered exclusively through the Jenkins CI/CD pipeline. No direct `helm upgrade` from laptops against shared environments. | ✅ Agreed |

---

## 3. Microservice Requirements

| ID | Requirement | Status |
|---|---|---|
| MS-001 | The system shall decompose into exactly **14 independent microservices**: `identity-service`, `authz-service`, `project-service`, `data-fabric-service`, `analytics-service`, `llm-service`, `documentation-service`, `evaluation-service`, `graphrag-service`, `computation-service`, `agent-platform-service`, and associated pipeline step pods. | ✅ Agreed |
| MS-002 | Each microservice shall have its own repository structure: `api/` (REST handlers), `grpc/` (gRPC servicers), `services/` (domain logic), `models/` (Pydantic schemas), `Dockerfile`, `pyproject.toml`. | ✅ Agreed |
| MS-003 | Services shall never share DynamoDB tables or Redis keyspaces directly. All cross-service data access goes through the owning service's API. | ✅ Agreed |
| MS-004 | Each microservice shall be colour-coded in architecture diagrams: **REFACTOR** (amber — existing code being modified), **NEW** (green — net-new code), **DELETE** (red — code being removed). | ✅ Agreed |
| MS-005 | Each microservice node in diagrams shall display its software components. Components shall be colour-coded: **amber** = modify from existing, **green** = new code to create. | ✅ Agreed |
| MS-006 | A dedicated **web application hosting** microservice or S3-based SPA hosting shall be provided to serve the React frontend, enabling internal access to the single-page application. | ✅ Agreed |

---

## 4. Authentication & Authorisation Requirements

| ID | Requirement | Status |
|---|---|---|
| AUTH-001 | Authentication shall be replaced with AWS Cognito using PKCE OAuth2 flow. Legacy password login and bcrypt/passlib shall be removed. | ✅ Agreed |
| AUTH-002 | There shall be a dedicated `identity-service` responsible for: Cognito PKCE exchange, MIDAS session JWT issuance, session lifecycle, JWKS endpoint. | ✅ Agreed |
| AUTH-003 | There shall be a dedicated `authz-service` responsible for RBAC: role definitions, permission definitions, user-role assignments, and `CheckPermission` gRPC RPC. | ✅ Agreed |
| AUTH-004 | Authentication (who you are) and authorisation (what you can do) shall be two separate services with no shared code path. | ✅ Agreed |
| AUTH-005 | Every protected operation in every service shall call `authz-service.CheckPermission` before proceeding. No service implements its own permission logic. | ✅ Agreed |
| AUTH-006 | RBAC roles shall include at minimum: `admin`, `analyst`, `viewer`, `data-steward`. | ✅ Agreed |
| AUTH-007 | JWT validation at the mesh boundary shall be handled by Istio `RequestAuthentication` using the JWKS endpoint provided by `identity-service`. | ✅ Agreed |
| AUTH-008 | The Cognito `access_token` shall never be forwarded downstream. Only the MIDAS session JWT shall be passed between services. | ✅ Agreed |

---

## 5. Data Management Requirements

| ID | Requirement | Status |
|---|---|---|
| DATA-001 | There shall be a dedicated `data-fabric-service` as the single owner of all data in MIDAS. No other service shall write to or read from S3 or AWS S3 Files directly. | ✅ Agreed |
| DATA-002 | `data-fabric-service` shall manage: dataset upload, format conversion (CSV/Excel → Parquet), train/test splits, preview, versioning, artefact registration, and data lineage. | ✅ Agreed |
| DATA-003 | `data-fabric-service` shall use AWS S3 Files (new service) for processed data, splits, and ML artefacts, providing POSIX-like access patterns between services. | ✅ Agreed |
| DATA-004 | Raw uploads (CSV/Excel) shall be stored in AWS S3 bucket `midas-raw/`. | ✅ Agreed |
| DATA-005 | Processed datasets and ML artefacts shall be stored in AWS S3 Files: `midas-datasets/parquet/`, `midas-datasets/splits/`, `midas-artefacts/{run_id}/`. | ✅ Agreed |
| DATA-006 | DynamoDB shall be used as the primary database, replacing all SQLite and Postgres raw SQL. There shall be 16 DynamoDB tables. | ✅ Agreed |
| DATA-007 | The `DataFrameStateManager` process singleton shall be deleted. DataFrames shall be cached in Redis (LZ4 compressed Parquet) with TTL=1800s. | ✅ Agreed |
| DATA-008 | Data lineage shall be tracked: `dataset → split → training-run → artefact`. | ✅ Agreed |

---

## 6. Computation & ML Pipeline Requirements

| ID | Requirement | Status |
|---|---|---|
| COMP-001 | All ML computation shall be delegated to `computation-service`, built as a facade over **Kubeflow Pipelines** on EKS. | ✅ Agreed |
| COMP-002 | The `BackgroundJobManager`, `training_jobs_state.json`, and `ThreadPoolExecutor` shall be deleted. Kubeflow Workflows replace all async ML execution. | ✅ Agreed |
| COMP-003 | `computation-service` shall provide a pipeline catalogue: CRUD operations for pipeline definitions, components, and functions. | ✅ Agreed |
| COMP-004 | Each pipeline step shall be an independently containerised `@kfp.component` function with its own Dockerfile and ECR image. | ✅ Agreed |
| COMP-005 | Pipeline step pods shall include: `feature-engineer`, `gbm-trainer`, `rfe-selector`, `auto-trainer`, `meea-evaluator`. Additional steps may be added. | ✅ Agreed |
| COMP-006 | GBM (Gradient Boosting Machine) training, including XGBoost, shall run inside the `gbm-trainer` pipeline component, triggered by `computation-service`, **not** directly in any other microservice. | ✅ Agreed |
| COMP-007 | Pipeline step pods shall retrieve data via `data-fabric-service` gRPC `GetDataframe` — never direct S3 access. | ✅ Agreed |
| COMP-008 | Pipeline step pods shall register trained model artefacts back to `data-fabric-service` via `RegisterArtefact` gRPC. | ✅ Agreed |
| COMP-009 | Training run progress shall be streamed to the client via SSE using a Redis pub/sub bridge (`train:progress:{run_id}`). | ✅ Agreed |
| COMP-010 | The end-to-end GBM training flow shall be clearly documented in the architecture, showing all actors, API calls, endpoints, and microservice components involved. | ✅ Agreed |

---

## 7. AI Agent Fabric Requirements

| ID | Requirement | Status |
|---|---|---|
| AGENT-001 | There shall be a dedicated `agent-platform-service` (NEW) providing an AI agent hosting and execution platform. | ✅ Agreed |
| AGENT-002 | `agent-platform-service` shall use AWS Bedrock AgentCore as the managed agent runtime, abstracting it behind an `AgentRuntimePort` interface. | ✅ Agreed |
| AGENT-003 | Agent workloads shall run on the EKS cluster in the `midas-agents` namespace as AgentCore microVM sessions. | ✅ Agreed |
| AGENT-004 | Every MIDAS platform capability shall be exposed as an Agent Tool via MCP (Model Context Protocol): data fabric, analytics, computation, LLM, GraphRAG, evaluation, project management, RBAC. | ✅ Agreed |
| AGENT-005 | There shall be 24 MCP platform tools covering all MIDAS services. | ✅ Agreed |
| AGENT-006 | RBAC shall be enforced on every agent tool call via `authz_tool.py → CheckPermission`. Agents cannot bypass permissions. | ✅ Agreed |
| AGENT-007 | Agents shall use the same REST/gRPC interfaces as human users — no special agent-only APIs in downstream services. | ✅ Agreed |
| AGENT-008 | The platform shall provide 5 out-of-the-box agents: `data-qa-agent`, `train-agent`, `insight-agent`, `doc-agent`, `pipeline-builder-agent`. | ✅ Agreed |
| AGENT-009 | Users and developers shall be able to create and register new custom agents via the platform API. | ✅ Agreed |
| AGENT-010 | AgentCore session management shall provide: session isolation (microVM per conversation), max session duration 8 hours, idle timeout 15 minutes, memory sanitisation on terminate. | ✅ Agreed |
| AGENT-011 | Long-term memory across sessions shall be supported via AgentCore Memory API. | ✅ Agreed |
| AGENT-012 | Agent run progress shall be streamable via SSE/WebSocket from `GET /agents/runs/{id}/stream`. | ✅ Agreed |
| AGENT-013 | `agent-platform-service` software components shall be: `agent_routes.py`, `tool_routes.py`, `memory_routes.py` (REST); `agent_servicer.py` (gRPC); `agentcore_service.py`, `tool_registry.py`, `memory_service.py`, `session_service.py`, `agent_catalogue_service.py` (services); 8 MCP tool adapters (tools/). | ✅ Agreed |

---

## 8. Ingress & Web Application Requirements

| ID | Requirement | Status |
|---|---|---|
| ING-001 | All browser traffic shall enter through AWS ALB (Application Load Balancer) as the single ingress point. | ✅ Agreed |
| ING-002 | An AWS WAF (Web Application Firewall) shall sit in front of the ALB, protecting the application boundary before any request reaches the Istio Ingress Gateway. | ✅ Agreed |
| ING-003 | The WAF shall enforce: OWASP Core Rule Set, rate limiting per IP per minute, geo-block rules, header inspection. WAF access logs shall be written to S3 `midas-waf-logs/`. | ✅ Agreed |
| ING-004 | The ALB shall handle TLS termination using an ACM-managed certificate. Traffic from ALB to cluster is HTTP. | ✅ Agreed |
| ING-005 | The Istio Ingress Gateway shall validate JWTs (using JWKS from `identity-service`), route requests to services by path prefix, and handle HTTP/1.1 → gRPC upgrade. | ✅ Agreed |
| ING-006 | The React SPA (single-page application) shall be hosted from AWS S3 and served via CloudFront or ALB, providing internal users a consistent web entry point. S3 website hosting ensures stateless, scalable frontend delivery with no frontend server pods. | ✅ Agreed |

---

## 9. Communication Protocol Requirements

| ID | Requirement | Status |
|---|---|---|
| COMM-001 | All service-to-service (internal) communication shall use **gRPC** (HTTP/2, Protocol Buffers). | ✅ Agreed |
| COMM-002 | All external communication (browser/CLI to service) shall use **RESTful HTTP/1.1 JSON** via the Istio Ingress Gateway. | ✅ Agreed |
| COMM-003 | No service shall expose both REST and gRPC for the same operation. | ✅ Agreed |
| COMM-004 | All `.proto` contract files and generated `_pb2.py` stubs shall reside in `midas-common/midas/proto/`. | ✅ Agreed |
| COMM-005 | Pre-built gRPC client wrappers shall be provided in `midas-common/midas/clients/` for all services. | ✅ Agreed |
| COMM-006 | Agent-to-service communication shall use MCP (Model Context Protocol) tool calls, which internally call the owning service's existing gRPC or REST interface. | ✅ Agreed |

---

## 10. Cloud Portability Requirements

| ID | Requirement | Status |
|---|---|---|
| PORT-001 | Application code shall never import `boto3` directly. All AWS service access shall be through port interfaces in `midas-common`. | ✅ Agreed |
| PORT-002 | The following port interfaces shall exist: `StoragePort`, `CachePort`, `NoSQLPort`, `SecretsPort`, `QueuePort`, `AgentRuntimePort`. | ✅ Agreed |
| PORT-003 | AWS adapter implementations shall exist for all ports: `S3StorageAdapter`, `S3FilesAdapter`, `DynamoDBAdapter`, `RedisAdapter`, `SecretsManagerAdapter`, `AgentCoreAdapter`. | ✅ Agreed |
| PORT-004 | Azure equivalents shall be achievable by swapping adapters only: Blob Storage → `StoragePort`, Cosmos DB → `NoSQLPort`, Azure Cache for Redis → `CachePort`, Azure AD B2C → identity adapter. | ✅ Documented |
| PORT-005 | GCP equivalents: GCS → `StoragePort`, Firestore → `NoSQLPort`, Memorystore Redis → `CachePort`. | ✅ Documented |

---

## 11. Security Requirements

| ID | Requirement | Status |
|---|---|---|
| SEC-001 | No secrets shall be stored in environment variables, container images, or git history. All secrets via AWS Secrets Manager only, accessed through `SecretsPort`. | ✅ Agreed |
| SEC-002 | Secrets Manager naming convention: `/midas/{service}/{key-name}`. | ✅ Agreed |
| SEC-003 | All pod-to-pod traffic shall use Istio mTLS STRICT. Default DENY ALL; explicit ALLOW per consumer pair. | ✅ Agreed |
| SEC-004 | Service accounts shall use IRSA. Each service has its own IAM role with least-privilege DynamoDB/S3/etc. permissions. | ✅ Agreed |
| SEC-005 | JWT signing keys shall be stored in Secrets Manager and rotated. No hardcoded `SECRET_KEY`. | ✅ Agreed |
| SEC-006 | WAF shall protect all inbound HTTP traffic before it reaches the Istio gateway. | ✅ Agreed |

---

## 12. Caching Requirements

| ID | Requirement | Status |
|---|---|---|
| CACHE-001 | ElastiCache Redis shall be the sole caching layer. | ✅ Agreed |
| CACHE-002 | The following cache key patterns shall be implemented with their TTLs: `session:{jti}` TTL=3600s, `authz:{uid}:{res}` TTL=300s, `df:{dataset_id}:{scope}` TTL=1800s, `llm-sel:{session_id}` TTL=session, `train:progress:{run_id}` (pub/sub), `agent:active:{session_id}`, `agent:progress:{run_id}`. | ✅ Agreed |
| CACHE-003 | In-process Python dicts used for caching (e.g. `_session_selections`) shall be replaced with Redis. | ✅ Agreed |
| CACHE-004 | DataFrames cached in Redis shall be LZ4-compressed Parquet bytes. | ✅ Agreed |

---

## 13. Observability Requirements

| ID | Requirement | Status |
|---|---|---|
| OBS-001 | Distributed tracing shall be implemented using Jaeger via Istio sidecar. | ✅ Agreed |
| OBS-002 | Metrics shall be exported to AWS CloudWatch. | ✅ Agreed |
| OBS-003 | Access logs shall be stored in S3. | ✅ Agreed |
| OBS-004 | A Kiali service graph shall be available for visualising service-to-service traffic. | ✅ Agreed |

---

## 14. Developer Experience Requirements

| ID | Requirement | Status |
|---|---|---|
| DEV-001 | The architecture documentation shall be developer-centric, clearly showing which code files must be refactored, which must be created new, and which must be deleted. | ✅ Agreed |
| DEV-002 | Every software component in architecture diagrams shall be colour-coded: **amber/yellow** = existing code to refactor/modify, **green** = new code to write, **red** = code to delete. | ✅ Agreed |
| DEV-003 | Microservices in diagrams shall be colour-coded: **yellow border** = contains refactored code, **green border** = entirely new service, **red** = to be deleted. | ✅ Agreed |
| DEV-004 | A complete end-to-end GBM model training flow shall be documented, covering all actors, API calls, endpoints, and microservice components from web UI to pipeline execution. | ✅ Agreed |
| DEV-005 | Hovering over any node in an architecture diagram shall show a short tooltip with the service description, software components, and whether components are new or modified. | ✅ Agreed |
| DEV-006 | Clicking on a node in an architecture diagram shall expand a full detail panel below the diagram with complete component descriptions, endpoints, and code file references. | ✅ Agreed |
| DEV-007 | Architecture diagrams shall be available as interactive HTML pages navigable from a shared sidebar. | ✅ Agreed |
| DEV-008 | Clicking a component in any diagram page shall navigate/link to its corresponding detail in the System Layer Diagram. | ✅ Agreed |

---

## 15. Diagram & Documentation Requirements

| ID | Requirement | Status |
|---|---|---|
| DIAG-001 | A **System Layer Diagram** shall show all layers (Client, Ingress, Mesh, Identity, Business, Agent, Data Fabric, Computation, Portability, Stores) as collapsible bands with service cards. | ✅ Delivered |
| DIAG-002 | An **SVG Component Diagram** shall show all 14 microservices and infrastructure in a single SVG with clickable nodes and hover tooltips. | ✅ Delivered |
| DIAG-003 | A **Classic Architecture Diagram** shall show all components in a column layout matching traditional enterprise architecture diagram style. | ✅ Delivered |
| DIAG-004 | A **Layered Architecture Diagram** shall show components in the style of the reference image (Clients → Ingress bar → Central Server Block with sub-layers → Stores). | ✅ Delivered |
| DIAG-005 | A **Microservice Software Component Diagram** shall show all 14 microservices with their individual software components colour-coded by status (new/refactor), with two central layers (Data Fabric, Computation Fabric) and the Service Mesh as cross-cutting. Other microservices orbit these central layers. | ✅ Agreed |
| DIAG-006 | The microservice diagram shall show end-to-end flows: web browser → action → data → GBM training pipeline trigger. | ✅ Agreed |
| DIAG-007 | Hovering a node shows a brief tooltip. Clicking a node expands a full detail panel at the bottom of the diagram. | ✅ Agreed |
| DIAG-008 | All diagrams shall use the same light-theme styling (classic palette) and share a consistent left-side navigation sidebar. | ✅ Agreed |

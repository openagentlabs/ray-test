# AWS Networking Reference — EXLDecision DEV

> **Purpose:** Quick-reference for software developers showing the complete networking stack:
> account → VPC → subnets → load balancers → TLS certificates → URL routing → Kubernetes pods.
>
> **Region:** `us-east-1` | **Account:** `811391286931` | **Last updated:** 2026-04-29

---

## Table of Contents

1. [Account & VPC](#1-account--vpc)
2. [Subnets](#2-subnets)
3. [Load Balancers Overview](#3-load-balancers-overview)
4. [TLS Certificates](#4-tls-certificates)
5. [MIDAS Application Stack — Traffic Flow](#5-midas-application-stack--traffic-flow)
   - [NLB → ALB Forwarding](#51-nlb--alb-forwarding)
   - [ALB Listener Rules & URL Routing](#52-alb-listener-rules--url-routing)
   - [ALB → Kubernetes Pod Mapping](#53-alb--kubernetes-pod-mapping)
6. [AI Gateway Stack — Traffic Flow](#6-ai-gateway-stack--traffic-flow)
7. [Kubernetes Cluster](#7-kubernetes-cluster)
8. [Pod → VPC & Subnet Placement](#8-pod--vpc--subnet-placement)
9. [Full Architecture Diagram (ASCII)](#9-full-architecture-diagram-ascii)

> **TOC links:** Fragment targets match **GitHub** auto-generated heading IDs (`github-slugger`: e.g. `&` and em dashes become `--`, `5.1` → `51-`). They work on **github.com**. If your **local** Markdown preview does not jump, the preview is using a different slugify mode—set it to **GitHub** (e.g. Markdown All in One `toc.slugifyMode`: `github`) or view the file on GitHub.

---

## 1. Account & VPC

| Field        | Value                                                       |
|---|---|
| AWS Account  | `811391286931`                                              |
| Region       | `us-east-1`                                                 |
| VPC ID       | `vpc-0c4d673f3e95a93eb`                                     |
| VPC Name     | `aws03-811391286931-ins-ai-MIDAS-DEV-DEV-vpc`               |
| CIDR Block   | `10.72.134.0/23`  (512 IPs: `10.72.134.0` – `10.72.135.255`) |
| Internet GW  | **None** — fully private; egress via Transit Gateway        |
| Transit GW   | `tgw-0ec391fa73943d562`                                     |

> **Key point:** There are no public subnets, no NAT Gateways, and no Internet Gateways. All load balancers are `internal` scheme. External traffic enters via the corporate network through the Transit Gateway.

---

## 2. Subnets

All subnets are **private** (no public IP assignment). They are split across two Availability Zones — `us-east-1a` and `us-east-1c` — for high availability.

| # | Subnet ID                  | CIDR               | AZ           | Size | Short Name   |
|---|---|----|---|---|---|
| 1 | `subnet-05c4fce53e16da9bc` | `10.72.134.0/25`   | us-east-1a   | 128  | az1-subnet-1 |
| 2 | `subnet-04d9f5b09b2dc9425` | `10.72.134.128/25` | us-east-1c   | 128  | az2-subnet-2 |
| 3 | `subnet-0bc74e29f773eb7a4` | `10.72.135.0/26`   | us-east-1a   | 64   | az1-subnet-3 |
| 4 | `subnet-04f6c506a5098aa40` | `10.72.135.64/26`  | us-east-1c   | 64   | az2-subnet-4 |
| 5 | `subnet-0636beaf9f48cc482` | `10.72.135.128/28` | us-east-1a   | 16   | az1-subnet-5 |
| 6 | `subnet-031582c139ff6d856` | `10.72.135.144/28` | us-east-1c   | 16   | az2-subnet-6 |
| 7 | `subnet-0ccf59f981ef4a1fb` | `10.72.135.160/28` | us-east-1a   | 16   | az1-subnet-7 |
| 8 | `subnet-0a0033f297fb483a5` | `10.72.135.176/28` | us-east-1c   | 16   | az2-subnet-8 |
| 9 | `subnet-0ff03c3d23aa03318` | `10.72.135.192/28` | us-east-1a   | 16   | az1-subnet-9 |
|10 | `subnet-0b79259b9522539b9` | `10.72.135.208/28` | us-east-1c   | 16   | az2-subnet-10|

> **EKS nodes** use subnets 1 & 2 (the two largest `/25` blocks, one per AZ).  
> **ALB/NLB** also use subnets 1 & 2 for cross-AZ distribution.

---

## 3. Load Balancers Overview

There are **two stacks** of load balancers sharing the same VPC:

| Stack           | Purpose                                         |
|---|---|
| **MIDAS**       | The EXLDecision analytics application (frontend, backend, graph) |
| **AI Gateway**  | Separate AI Gateway services (C1 API, LiteLLM, Langfuse) — owned by Unified-Cloud-DevOps |

### 3.1 All Load Balancers

| Name                          | Type    | Scheme   | DNS (internal)                                                                  | Status |
|---|---|---|---|---|
| `midas-dev-nlb`               | NLB     | internal | `midas-dev-nlb-d290764c37bb4f68.elb.us-east-1.amazonaws.com`                   | active |
| `midas-dev-alb`               | ALB     | internal | `internal-midas-dev-alb-2046892741.us-east-1.elb.amazonaws.com`                | active |
| `midas-eks-aigtw-dev-nlb-c1-api`    | NLB | internal | `midas-eks-aigtw-dev-nlb-c1-api-56e7d2385a7dd47c.elb.us-east-1.amazonaws.com` | active |
| `midas-eks-aigtw-dev-nlb-litellm`   | NLB | internal | `midas-eks-aigtw-dev-nlb-litellm-763683b0e22d535d.elb.us-east-1.amazonaws.com`| active |
| `midas-eks-aigtw-dev-nlb-langfuse`  | NLB | internal | `midas-eks-aigtw-dev-nlb-langfuse-802b6dbefa654364.elb.us-east-1.amazonaws.com`| active |
| `midas-aigtw-c1-api-alb-dev`  | ALB     | internal | `internal-midas-aigtw-c1-api-alb-dev-43367903.us-east-1.elb.amazonaws.com`     | active |
| `midas-aigtw-litellm-alb-dev` | ALB     | internal | `internal-midas-aigtw-litellm-alb-dev-398260702.us-east-1.elb.amazonaws.com`   | active |
| `midas-aigtw-langfuse-alb-dev`| ALB     | internal | `internal-midas-aigtw-langfuse-alb-dev-837475564.us-east-1.elb.amazonaws.com`  | active |

> All load balancers are `internal` — they are reachable only from within the VPC or via the corporate network through the Transit Gateway.

---

## 4. TLS Certificates

Managed by AWS Certificate Manager (ACM) in `us-east-1`.

| Certificate Domain                          | Status             | Used By                                                   |
|---|---|---|
| `midas-aigtw-control-api-dev.exlservice.com` | ✅ ISSUED           | `midas-dev-alb` + `midas-aigtw-c1-api-alb-dev`           |
| `exldecision-ai-dev-aigw-c1.exlservice.com`  | ⏳ PENDING_VALIDATION | Not yet attached to any load balancer                   |
| `exldecision-ai-dev-aigw-langfuse.exlservice.com` | ⏳ PENDING_VALIDATION | Not yet attached to any load balancer               |
| `exldecision-ai-dev-aigw-litellm.exlservice.com`  | ⏳ PENDING_VALIDATION | Not yet attached to any load balancer               |

### 4.1 Certificate → URL Mapping

| Certificate                                     | Hostname (SAN)                                | Load Balancer                  |
|---|---|---|
| `9242f7d2-b91c-4517-9548-28936fdf8cf6` (ISSUED) | `midas-aigtw-control-api-dev.exlservice.com`  | `midas-dev-alb` (MIDAS app)    |
| `9242f7d2-b91c-4517-9548-28936fdf8cf6` (ISSUED) | `midas-aigtw-control-api-dev.exlservice.com`  | `midas-aigtw-c1-api-alb-dev`   |

> **Note:** The three `PENDING_VALIDATION` certificates are provisioned but DNS validation has not yet completed. They are not serving traffic.

---

## 5. MIDAS Application Stack — Traffic Flow

The MIDAS app uses a **two-tier** load balancing pattern: an NLB as the outer TLS pass-through layer, forwarding to an ALB that handles HTTPS termination and path-based routing.

```
Corporate Network / Transit Gateway
         │
         ▼ TCP:443
  ┌─────────────────┐
  │   midas-dev-nlb  │   (Network Load Balancer)
  │   TCP:443        │   Passes TLS to ALB unchanged
  └────────┬────────┘
           │ TCP forward → ALB:443
           ▼
  ┌─────────────────────────────────────────────────────┐
  │              midas-dev-alb                          │
  │  HTTPS:443  │  Cert: midas-aigtw-control-api-dev... │
  │  TLS terminated here; path-based routing below      │
  └─────────────────────────────────────────────────────┘
```

### 5.1 NLB → ALB Forwarding

| NLB            | Listener | Protocol | Target                  | Target Type |
|---|---|---|---|---|
| `midas-dev-nlb` | `:443`  | TCP      | `midas-dev-alb` port 443 | ALB (by ARN) |

The NLB's single target group (`midas-dev-nlb-alb-tg`) points directly at the ALB's ARN — **target health: healthy**.

### 5.2 ALB Listener Rules & URL Routing

The ALB has a single HTTPS listener on port 443. Rules are evaluated in priority order:

| Priority | Host Header                                           | Path Pattern     | Action                    | URL Rewrite          |
|---|---|---|---|---|
| 10       | `exldecision-ai-dev.exlservice.com` or ALB DNS       | `/frontend` or `/frontend/*` | → Frontend TG (port 8080) | `/frontend/foo` → `/foo` |
| 20       | `exldecision-ai-dev.exlservice.com` or ALB DNS       | `/backend` or `/backend/*`   | → Backend TG (port 8000)  | `/backend/foo` → `/foo`  |
| 30       | `exldecision-ai-dev.exlservice.com` or ALB DNS       | `/graph` or `/graph/*`       | → Graph TG (port 8001)    | `/graph/foo` → `/foo`    |
| default  | (any)                                                | (any)            | → Frontend TG (port 8080) | none                     |

> **Path rewriting:** The ALB strips the prefix before forwarding. A request to `/backend/api/v1/health` arrives at the backend pod as `/api/v1/health`.

### 5.3 ALB → Kubernetes Pod Mapping

| Target Group         | Port | Protocol | Pod (K8s Service)               | Pod IP          | Health Check | Status   |
|---|---|---|---|---|---|---|
| `midas-dev-alb-fe-tg` | 8080 | HTTP | `midas-web-frontend-svc`         | `10.72.134.24`  | `/`          | ✅ healthy |
| `midas-dev-alb-be-tg` | 8000 | HTTP | `midas-api-backend-svc`          | `10.72.134.104` | `/`          | ✅ healthy |
| `midas-dev-alb-gr-tg` | 8001 | HTTP | `midas-graph-svc`                | `10.72.134.187` | `/`          | ✅ healthy |

#### Kubernetes Services (ClusterIP)

| K8s Service                 | ClusterIP       | Port | Pod Container Port | Namespace   |
|---|---|---|---|---|
| `midas-web-frontend-svc`    | `172.20.43.187` | 8080 | 8080               | `midas-apps` |
| `midas-api-backend-svc`     | `172.20.153.10` | 8000 | 8000               | `midas-apps` |
| `midas-graph-svc`           | `172.20.92.23`  | 8001 | 8001               | `midas-apps` |

#### Complete URL → Pod Mapping

| Public URL (via NLB entry)                               | Routes To Pod           | Pod Port |
|---|---|---|
| `https://exldecision-ai-dev.exlservice.com/`             | `midas-web-frontend-svc` | 8080    |
| `https://exldecision-ai-dev.exlservice.com/frontend/*`   | `midas-web-frontend-svc` | 8080    |
| `https://exldecision-ai-dev.exlservice.com/backend/*`    | `midas-api-backend-svc`  | 8000    |
| `https://exldecision-ai-dev.exlservice.com/graph/*`      | `midas-graph-svc`        | 8001    |

---

## 6. AI Gateway Stack — Traffic Flow

The AI Gateway is a separate stack (owned by Unified-Cloud-DevOps) running in the same VPC. It has its own NLB + ALB pairs per service.

| Service  | NLB                               | ALB                            | Public Hostname (pending cert)                  |
|---|---|---|---|
| C1 API   | `midas-eks-aigtw-dev-nlb-c1-api`  | `midas-aigtw-c1-api-alb-dev`   | `exldecision-ai-dev-aigw-c1.exlservice.com`      |
| LiteLLM  | `midas-eks-aigtw-dev-nlb-litellm` | `midas-aigtw-litellm-alb-dev`  | `exldecision-ai-dev-aigw-litellm.exlservice.com` |
| Langfuse | `midas-eks-aigtw-dev-nlb-langfuse`| `midas-aigtw-langfuse-alb-dev` | `exldecision-ai-dev-aigw-langfuse.exlservice.com`|

### AI Gateway ALB Listener Configuration

| ALB                          | Port 80       | Port 443  | Certificate                            | Default Action |
|---|---|---|---|---|
| `midas-aigtw-c1-api-alb-dev` | 301 → HTTPS   | HTTPS ✅  | `midas-aigtw-control-api-dev...` (ISSUED) | 404 fixed response |
| `midas-aigtw-litellm-alb-dev`| 301 → HTTPS   | —         | pending cert (PENDING_VALIDATION)      | — |
| `midas-aigtw-langfuse-alb-dev`| —            | —         | pending cert (PENDING_VALIDATION)      | — |

> **Note:** The AI Gateway NLBs currently have **no listeners configured** (empty listener list) and the three pending certificates have not yet passed DNS validation. The AI Gateway is not yet serving external traffic on the new hostnames.

### AI Gateway Target Group → Pod Mapping

| Target Group                      | Health Check Path       | K8s Namespace | K8s Service     |
|---|---|---|---|
| `k8s-c1api-controla-891e957e1e`   | `/api/health`           | `c1api`       | `control-api`   |
| `k8s-litellm-litellm-08817b12f5`  | `/health/liveliness`    | `litellm`     | `litellm`       |
| `k8s-langfuse-langfuse-28d92849ba`| `/api/public/health`    | `langfuse`    | `langfuse`      |

---

## 7. Kubernetes Cluster

### Cluster

| Field          | Value                                          |
|---|---|
| Cluster Name   | `midas-eks-dev`                                |
| Kubernetes Ver | `1.30`                                         |
| EKS Access     | Private API endpoint only (inside VPC)         |
| OIDC Provider  | `oidc.eks.us-east-1.amazonaws.com/id/D215BDB7961B3419B289036FAEC57DC8` |

### Node Group

| Field         | Value                    |
|---|---|
| Name          | `midas-eks-dev-ng`       |
| Instance Type | `m6i.4xlarge`           |
| Desired Nodes | 2                        |
| Min / Max     | 1 / 4                    |
| Subnets       | `subnet-04d9f5b09b2dc9425` (az1c), `subnet-05c4fce53e16da9bc` (az1a) |
| AMI Type      | `AL2_x86_64`             |
| Disk          | 50 GB per node           |
| Status        | ACTIVE                   |

### Running Pods (midas-apps namespace)

| Pod                                      | Node IP         | Pod IP          | Status  | Restarts |
|---|---|---|---|---|
| `midas-api-backend-svc-*`                | `10.72.134.106` | `10.72.134.104` | Running | 0        |
| `midas-graph-svc-*`                      | `10.72.134.157` | `10.72.134.187` | Running | 0        |
| `midas-web-frontend-svc-*`               | `10.72.134.106` | `10.72.134.24`  | Running | 0        |

---

## 8. Pod → VPC & Subnet Placement

This section maps every application pod to its exact position in the VPC: which EKS cluster it runs in, which EC2 node hosts it, which subnet that node sits in, and what IP the pod receives from that subnet's CIDR range.

### 8.1 How Pod IP addressing works

Each EKS node is placed in a subnet. The AWS VPC CNI plugin assigns pod IPs directly from the **same subnet CIDR as the node** — pods are first-class VPC citizens with real VPC IPs, not a secondary overlay network.

```
VPC CIDR: 10.72.134.0/23
          │
          ├─ subnet-05c4fce53e16da9bc  10.72.134.0/25   (us-east-1a)
          │     └─ EKS Node 10.72.134.106  ← Node IP from this subnet
          │           ├─ Pod: midas-web-frontend-svc   10.72.134.24
          │           └─ Pod: midas-api-backend-svc    10.72.134.104
          │
          └─ subnet-04d9f5b09b2dc9425  10.72.134.128/25 (us-east-1c)
                └─ EKS Node 10.72.134.157  ← Node IP from this subnet
                      └─ Pod: midas-graph-svc           10.72.134.187
```

### 8.2 MIDAS Application Pods — Subnet Placement

| Pod | Service | Namespace | Pod IP | Node IP | Node Instance | Subnet ID | Subnet CIDR | AZ |
|---|---|---|---|---|---|---|---|---|
| `midas-web-frontend-svc-*` | Frontend (React) | `midas-apps` | `10.72.134.24` | `10.72.134.106` | `i-062671a1f4fa68023` | `subnet-05c4fce53e16da9bc` | `10.72.134.0/25` | us-east-1a |
| `midas-api-backend-svc-*` | Backend (FastAPI) | `midas-apps` | `10.72.134.104` | `10.72.134.106` | `i-062671a1f4fa68023` | `subnet-05c4fce53e16da9bc` | `10.72.134.0/25` | us-east-1a |
| `midas-graph-svc-*` | Graph API | `midas-apps` | `10.72.134.187` | `10.72.134.157` | `i-0d53f3cc3bf8bc461` | `subnet-04d9f5b09b2dc9425` | `10.72.134.128/25` | us-east-1c |

> **Note:** Frontend and Backend pods currently share the same node (`10.72.134.106` in `us-east-1a`). Graph runs on the second node (`10.72.134.157` in `us-east-1c`). Pod placement is managed by the Kubernetes scheduler and will shift when pods are rescheduled — the subnet assignment follows the node, not the pod.

### 8.3 AI Gateway Pods — Subnet Placement

The AI Gateway runs in a **separate EKS cluster** (`midas-eks-aigtw-dev`, Kubernetes 1.35) but in the **same VPC and same subnets**. Its nodes also use the two primary `/25` subnets.

| Service | K8s Namespace | EKS Cluster | Node IP | Node Instance | Instance Type | Subnet ID | Subnet CIDR | AZ |
|---|---|---|---|---|---|---|---|---|
| LiteLLM | `litellm` | `midas-eks-aigtw-dev` | `10.72.134.52` | `i-05c65c9129758a6c4` | `m6i.xlarge` | `subnet-05c4fce53e16da9bc` | `10.72.134.0/25` | us-east-1a |
| LiteLLM | `litellm` | `midas-eks-aigtw-dev` | `10.72.134.70` | `i-0b4e774ac9fcddd68` | `t3.large` | `subnet-05c4fce53e16da9bc` | `10.72.134.0/25` | us-east-1a |
| Langfuse | `langfuse` | `midas-eks-aigtw-dev` | `10.72.134.196` | `i-006f4dcd521406d35` | `m6i.xlarge` | `subnet-04d9f5b09b2dc9425` | `10.72.134.128/25` | us-east-1c |
| Langfuse | `langfuse` | `midas-eks-aigtw-dev` | `10.72.134.148` | `i-06a6f48d6f4277f2a` | `t3.large` | `subnet-04d9f5b09b2dc9425` | `10.72.134.128/25` | us-east-1c |
| C1 API   | `c1api` | `midas-eks-aigtw-dev` | `10.72.134.229` | `i-0658b278f71d1a78a` | `t3.large` | `subnet-04d9f5b09b2dc9425` | `10.72.134.128/25` | us-east-1c |

> **Note:** Pod IPs for the AI Gateway services are derived from the same VPC subnets. Access to `midas-eks-aigtw-dev` pods is restricted — the MIDAS jumpbox role does not have access to this cluster's API server.

### 8.4 All Pods — Consolidated View

This single table gives the full picture across both stacks.

| Pod / Service | Stack | Cluster | Pod IP | Subnet CIDR | AZ | Container Port | Public URL |
|---|---|---|---|---|---|---|---|
| `midas-web-frontend-svc` | MIDAS | `midas-eks-dev` | `10.72.134.24` | `10.72.134.0/25` | us-east-1a | 8080 | `exldecision-ai-dev.exlservice.com/frontend/*` |
| `midas-api-backend-svc` | MIDAS | `midas-eks-dev` | `10.72.134.104` | `10.72.134.0/25` | us-east-1a | 8000 | `exldecision-ai-dev.exlservice.com/backend/*` |
| `midas-graph-svc` | MIDAS | `midas-eks-dev` | `10.72.134.187` | `10.72.134.128/25` | us-east-1c | 8001 | `exldecision-ai-dev.exlservice.com/graph/*` |
| LiteLLM | AI Gateway | `midas-eks-aigtw-dev` | `10.72.134.52 / .70` | `10.72.134.0/25` | us-east-1a | — | `exldecision-ai-dev-aigw-litellm.exlservice.com` *(pending)* |
| Langfuse | AI Gateway | `midas-eks-aigtw-dev` | `10.72.134.148 / .196` | `10.72.134.128/25` | us-east-1c | — | `exldecision-ai-dev-aigw-langfuse.exlservice.com` *(pending)* |
| C1 API | AI Gateway | `midas-eks-aigtw-dev` | `10.72.134.229` | `10.72.134.128/25` | us-east-1c | — | `exldecision-ai-dev-aigw-c1.exlservice.com` *(pending)* |

### 8.5 Subnet Usage Summary

| Subnet ID | CIDR | AZ | Hosts (nodes) | Pods running here |
|---|---|---|---|---|
| `subnet-05c4fce53e16da9bc` | `10.72.134.0/25` | us-east-1a | MIDAS node `10.72.134.106`, AI GW nodes `10.72.134.52`, `10.72.134.70` | Frontend, Backend (MIDAS) · LiteLLM (AI GW) |
| `subnet-04d9f5b09b2dc9425` | `10.72.134.128/25` | us-east-1c | MIDAS node `10.72.134.157`, AI GW nodes `10.72.134.148`, `10.72.134.196`, `10.72.134.229` | Graph (MIDAS) · Langfuse, C1 API (AI GW) |

> Both stacks share the same two primary `/25` subnets — one per AZ. The VPC CIDR `10.72.134.0/23` provides 512 IPs total across all subnets, with the two `/25` blocks (`/128` IPs each) carrying all workloads.

---

## 9. Full Architecture Diagram (ASCII)

```
                     CORPORATE NETWORK / TRANSIT GATEWAY
                               │
                 ──────────────────────────────────────────
                 │               VPC: 10.72.134.0/23       │
                 │                                          │
                 │   ┌──────────────────────────────────┐   │
                 │   │  MIDAS APP STACK                 │   │
                 │   │                                  │   │
                 │   │  ┌─────────────────────────┐    │   │
                 │   │  │  midas-dev-nlb           │    │   │
                 │   │  │  Network LB (TCP:443)    │    │   │
                 │   │  │  internal                │    │   │
                 │   │  └────────────┬────────────┘    │   │
                 │   │               │ TCP:443           │   │
                 │   │               ▼                   │   │
                 │   │  ┌─────────────────────────┐    │   │
                 │   │  │  midas-dev-alb           │    │   │
                 │   │  │  App LB (HTTPS:443)      │    │   │
                 │   │  │  TLS: *.exlservice.com   │    │   │
                 │   │  │                          │    │   │
                 │   │  │  Path routing:           │    │   │
                 │   │  │  /frontend/* ──────────────────────────► midas-web-frontend-svc :8080
                 │   │  │  /backend/*  ──────────────────────────► midas-api-backend-svc  :8000
                 │   │  │  /graph/*    ──────────────────────────► midas-graph-svc        :8001
                 │   │  │  /* (default) ─────────────────────────► midas-web-frontend-svc :8080
                 │   │  └─────────────────────────┘    │   │
                 │   └──────────────────────────────────┘   │
                 │                                           │
                 │   ┌──────────────────────────────────┐   │
                 │   │  AI GATEWAY STACK                │   │
                 │   │  (managed by Unified-Cloud-DevOps)│  │
                 │   │                                  │   │
                 │   │  ┌───────────────────┐           │   │
                 │   │  │ NLB: c1-api       │──► ALB ──►│   K8s: control-api pod (c1api ns)
                 │   │  │ NLB: litellm      │──► ALB ──►│   K8s: litellm pod     (litellm ns)
                 │   │  │ NLB: langfuse     │──► ALB ──►│   K8s: langfuse pod    (langfuse ns)
                 │   │  └───────────────────┘           │   │
                 │   └──────────────────────────────────┘   │
                 │                                           │
                 │   ┌──────────────────────────────────┐   │
                 │   │  EKS CLUSTER: midas-eks-dev      │   │
                 │   │  Node Group: midas-eks-dev-ng    │   │
                 │   │  2 x m6i.4xlarge (min:1 max:4)   │   │
                 │   │                                  │   │
                 │   │  Node 1: 10.72.134.106 (az1c)    │   │
                 │   │    └─ midas-api-backend-svc pod  │   │
                 │   │    └─ midas-web-frontend-svc pod │   │
                 │   │  Node 2: 10.72.134.157 (az1a)    │   │
                 │   │    └─ midas-graph-svc pod        │   │
                 │   └──────────────────────────────────┘   │
                 │                                           │
                 ─────────────────────────────────────────────
```

### Simplified Request Flow

```
Browser / Client
     │
     │ HTTPS to: exldecision-ai-dev.exlservice.com
     ▼
Corporate DNS → resolves to NLB private IP
     │
     ▼ TCP:443
midas-dev-nlb  (passes through, no TLS termination)
     │
     ▼ TCP:443
midas-dev-alb  (terminates TLS, reads URL path)
     │
     ├─ /frontend/*  ──► midas-web-frontend-svc  ──► Pod :8080  (React SPA)
     ├─ /backend/*   ──► midas-api-backend-svc   ──► Pod :8000  (FastAPI)
     ├─ /graph/*     ──► midas-graph-svc         ──► Pod :8001  (Graph API)
     └─ /*           ──► midas-web-frontend-svc  ──► Pod :8080  (default)
```

---

## Quick Reference

| What you want to reach      | URL / Entry Point                                      |
|---|---|
| Application (browser)        | `https://exldecision-ai-dev.exlservice.com`            |
| Backend API docs (Swagger)   | `https://exldecision-ai-dev.exlservice.com/backend/docs` |
| Backend health check         | `https://exldecision-ai-dev.exlservice.com/backend/health` |
| Graph API                    | `https://exldecision-ai-dev.exlservice.com/graph/`     |
| Jumpbox (SSM)                | `aws ssm start-session --target i-0219e5e54f6d187b4`   |
| EKS cluster                  | `aws eks update-kubeconfig --name midas-eks-dev`       |

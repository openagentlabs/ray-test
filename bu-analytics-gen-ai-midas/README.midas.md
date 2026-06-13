<!--
  EXLdecision Solution Documentation — Long-form MIDAS overview.
  Previously served as the repository root README; renamed to keep it
  available without it being shown by the git host. The git host now
  renders ./README.md (the Atlas landing page).
  Maintained by the BU Analytics / Gen-AI EXLdecision team.
  Follow .cursor/rules/doc.mdc when editing this file.
-->

<div align="center">

  <img src="docs/images/exl-service-logo.png" alt="EXL Service" width="280" /><br/><br/>

  # EXLdecision.AI
  ## Using advanced AI to intelligently mine your data, transforming it into actionable decisions

  > *Transform your data into decisions using AI — private, secure, and AI-first.*

  <br/>

  ![Version](https://img.shields.io/badge/version-1.2.3-blue?style=flat-square)
  ![Status](https://img.shields.io/badge/status-Active-brightgreen?style=flat-square)
  ![Region](https://img.shields.io/badge/AWS-us--east-1-orange?style=flat-square)
  ![Platform](https://img.shields.io/badge/platform-EKS%20%7C%20ECS-informational?style=flat-square)
  ![Pipeline](https://img.shields.io/badge/deploy-Jenkins%20CI%2FCD-yellow?style=flat-square)

</div>

---

<div align="center">

| Field | Value |
|---|---|
| **Document** | EXLdecision Solution Documentation — Master README |
| **Version** | `1.2.3` |
| **Status** | Active |
| **Date** | 2026-04-18 |
| **Author** | BU Analytics / Gen-AI EXLdecision team |
| **Contact** | `keith.tobin@exlservice.com` |
| **Repository** | `bu-analytics-gen-ai-midas` |
| **Business unit** | BU Analytics · EXL Service |
| **Infrastructure** | [**Solution infrastructure overview →**](docs/infrastructure.md) |

</div>

---

## Table of Contents

- [1. Overview](#1-overview)
- [2. Document Index](#2-document-index)
  - [2.1 Core deploy and infrastructure](#21-core-deploy-and-infrastructure)
  - [2.2 Standards and conventions](#22-standards-and-conventions)
  - [2.3 Operational and network docs](#23-operational-and-network-docs)
  - [2.4 Cursor IDE workspace (`.cursor`)](#24-cursor-ide-workspace-cursor)
- [3. Getting Started](#3-getting-started)
  - [3.1 Prerequisites](#31-prerequisites)
  - [3.2 Local development checks](#32-local-development-checks)
  - [3.3 Running the pipeline](#33-running-the-pipeline)
- [4. Repository Layout](#4-repository-layout)
- [5. Change Log](#5-change-log)
- [6. Appendix](#6-appendix)
  - [6.1 Glossary](#61-glossary)
  - [6.2 Architecture Decision Records](#62-architecture-decision-records-adrs)
  - [6.3 Reference links](#63-reference-links)

---

## 1. Overview

**EXLdecision** is EXL Service's Gen-AI analytics platform, deployed entirely on AWS (`us-east-1`). It provides a private, pipeline-driven infrastructure for running AI/ML inference workloads, RAG pipelines, data services, and analytics APIs — all inside a corporate VPC with zero public internet exposure.

### What EXLdecision does

| Capability | Description |
|---|---|
| **Gen-AI / RAG** | LangChain / LangGraph orchestration with Amazon Bedrock for model inference and embedding |
| **Private analytics APIs** | Internal REST/GraphQL APIs served via internal ALB over the corporate VPC |
| **Managed data layer** | S3, RDS/Aurora, ElastiCache, OpenSearch — all private, encrypted, and pipeline-provisioned |
| **Secure infrastructure** | EKS + ECS compute, KMS encryption, Secrets Manager, VPC PrivateLink endpoints throughout |
| **Automated delivery** | Jenkins CI/CD — build, test, Terraform apply, ECR push, Helm deploy — no manual applies |

> **Important:** All infrastructure changes reach shared environments **only via the Jenkins CI/CD pipeline** (`deploy/Jenkinsfile_Deploy_App`). Local `terraform apply` or `helm upgrade` against `dev`/`uat`/`prod` is not the default path and bypasses audit and approval controls.

---

## 2. Document Index

### 2.1 Core deploy and infrastructure

| Path | Purpose |
|---|---|
| [`docs/infrastructure.md`](docs/infrastructure.md) | **Platform overview** — accounts, VPC, network posture, pipelines, Well-Architected mapping, IaC conventions |
| [`deploy/README.md`](deploy/README.md) | Jenkins job, customer mapping, Terraform state keys, deployer role, module registration |
| [`deploy/ecs-app/docker/README.md`](deploy/ecs-app/docker/README.md) | Docker image contexts, ECR naming, build stages |
| [`deploy/ecs-app/docker/build-registry/README.md`](deploy/ecs-app/docker/build-registry/README.md) | **`images.yaml`** schema and CI consumption |
| [`deploy/ecs-app/helm/README.md`](deploy/ecs-app/helm/README.md) | Helm charts, **`releases.yaml`**, EKS deploy |
| [`deploy/scripts/README.md`](deploy/scripts/README.md) | **`deploy/scripts/`** layout (`ci/`, `dev/`, `test/`, `util/`), Jenkins vs ad-hoc tools, usage |
| [`.cursor/scripts/README.md`](.cursor/scripts/README.md) | Cursor-local Jenkins/EKS helpers (not the pipeline `deploy/scripts` tree) |

### 2.2 Standards and conventions

| Path | Purpose |
|---|---|
| [`docs/aws-resource-naming-conventions.md`](docs/aws-resource-naming-conventions.md) | **Mandatory** — AWS resource naming conventions for all EXLdecision environments. 100+ resource types across 13 categories, each with pattern, example, max length, and AWS docs link. 20 explicit naming rules (R01–R20). Must be consulted before creating any AWS resource. Current version: `2.2.0`. |

### 2.3 Operational and network docs

| Path | Purpose |
|---|---|
| [`docs/core-infrastructure-workorder-private-aws-services.md`](docs/core-infrastructure-workorder-private-aws-services.md) | Work order: private AWS service connectivity (EKS + data services) — P0/P1/P2 blockers |
| [`docs/workorder-vpc-endpoints-list.md`](docs/workorder-vpc-endpoints-list.md) | VPC endpoint reference list with Private DNS hostnames (`us-east-1`) |
| [`docs/network-connectivity-shared-request-2026-04-16.md`](docs/network-connectivity-shared-request-2026-04-16.md) | Shared infrastructure enablement request — EXLdecision DEV NLB |
| [`docs/eks-private-endpoint-check-results.md`](docs/eks-private-endpoint-check-results.md) | EKS private endpoint connectivity check results |
| [`docs/kt-check-endpoint-for-eks-node-attach.md`](docs/kt-check-endpoint-for-eks-node-attach.md) | EKS node attach endpoint check procedure |

### 2.4 Cursor IDE workspace (`.cursor`)

| Path | Purpose |
|---|---|
| [`.cursor/README.md`](.cursor/README.md) | **Folder guide** — what each top-level directory under **`.cursor/`** is for (`rules/`, `skills/`, `scripts/`, `tools/`, `validation/`, `config/`, `plans/`, and optional placeholders). |

### 2.5 AI Gateway

| Path | Purpose |
|---|---|
| [`docs/guardrails-developer-guide.md`](docs/guardrails-developer-guide.md) | **Guardrails developer guide** — how Bedrock Guardrails work in the LiteLLM AI Gateway; the 4 `exlerate-*` profiles, PII entity coverage (28 types), request flow, decision guide, test commands, and how to assign guardrails per team / key / request. Start here before working with any guardrail. |

Keep the index tables aligned when adding or removing first-class READMEs (see **`.cursor/rules/doc.mdc`**).

---

## 3. Getting Started

### 3.1 Prerequisites

| Tool | Minimum version | Notes |
|---|---|---|
| AWS CLI | `2.x` | Configured with SSO for account `811391286931` |
| Terraform | `>= 1.5` | Only used locally for `plan`; applies run via pipeline |
| kubectl | `>= 1.28` | For EKS cluster inspection |
| Helm | `>= 3.12` | For chart templating and local dry-runs |
| Docker | `>= 24.0` | For local image builds |
| Jenkins | Current LTS | Shared controller — not self-hosted by this team |

### 3.2 Local development checks

Read-only checks (plan, lint, template) are safe to run locally:

```bash
# Terraform plan — review only, do not apply locally against shared environments
cd deploy/ecs-app
terraform init -backend-config="bucket=<state-bucket>" -backend-config="key=<state-key>"
terraform plan -var="environment=dev" -var="aws_account_id=811391286931"

# Helm dry-run template
helm template midas deploy/ecs-app/helm/midas -f deploy/ecs-app/helm/midas/values-dev.yaml

# Connectivity — start with STS / identity (read-only); see skill for full suite
python3 deploy/scripts/util/validate-aws-cli-identity.py
```

### 3.3 Running the pipeline

All environment-changing operations must go through Jenkins:

1. Raise a PR and get at least one reviewer approval.
2. Merge to `main` (or the configured target branch).
3. Trigger **`Jenkinsfile_Deploy_App`** for the target environment parameter (`dev` / `uat` / `prod`).
4. Monitor the pipeline stages — **deploy-role Terraform → ecs-app Terraform → ECR push → Helm**.

> **Note:** Never run `terraform apply` or `helm upgrade` directly against `dev`, `uat`, or `prod` from a laptop. Local applies bypass the audit trail, approval gates, and state locking that the pipeline enforces.

---

## 4. Repository Layout

```
bu-analytics-gen-ai-midas/
├── README.md                       # This file — rendered on the Git host repo home page
├── .cursor/                        # Cursor IDE config — see .cursor/README.md
│   ├── README.md                   # Index of .cursor/ folders (rules, skills, scripts, …)
│   ├── rules/                      # Agent rules (.mdc)
│   ├── skills/                     # Agent skill definitions (SKILL.md per skill)
│   ├── scripts/                    # Cursor-local helper scripts (non-pipeline)
│   ├── tools/                      # Tool registry + scripts for skills
│   └── …                           # validation/, config/, plans/, … (see .cursor/README.md)
├── deploy/
│   ├── Jenkinsfile_Deploy_App       # Main application deploy pipeline
│   ├── Jenkinsfile_Build            # Image build pipeline
│   ├── Jenkinsfile_Deploy_Task_Definition
│   ├── deploy_role/                 # Deployer IAM role Terraform + policy files
│   │   └── iam-policy/             # midas-deployer-policy-001 … 010
│   └── ecs-app/                    # Application Terraform root (state bucket owned here)
│       ├── main.tf / *.tf          # Root module registration files
│       ├── modules/                # Reusable modules (s3/, kms/, sqs/, eks/, …)
│       ├── docker/                 # Docker contexts, ECR naming, build-registry/
│       └── helm/                   # Helm chart definitions and values per env
├── docs/                           # Human-readable solution documentation
│   ├── README.md                   # Short pointer when browsing docs/ on the Git host
│   ├── infrastructure.md           # Platform overview (AWS, network, pipelines, conventions)
│   └── images/                     # Documentation assets
│       └── exl-service-logo.png
└── src/                            # Application source code
```

---

IaC, Helm, ECR, IAM, and platform-level conventions are documented in [**`docs/infrastructure.md`**](docs/infrastructure.md#8-iac-images-and-runtime-conventions).

---

## 5. Change Log

All notable changes to the EXLdecision solution documentation and infrastructure are recorded here. Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

### [1.2.3] — 2026-04-18

#### Changed

- **`README.md` (repository root)** — canonical master README for Git hosting (GitHub / GitLab / Gitea render the root `README.md` on the repository home page, not `docs/README.md`). Content moved from `docs/README.md` with paths adjusted for the repo root; version `1.2.3`.
- **`docs/README.md`** — replaced with a short entry point that links to the root README so browsing the `docs/` folder still directs readers to the full guide.

---

### [1.2.2] — 2026-04-18

#### Added

- `docs/infrastructure.md` — platform overview (Well-Architected mapping, environment inventory, network, CI/CD, IaC conventions) with **MISSION** placeholders for gaps not yet documented in-repo.

#### Changed

- `docs/README.md` — cover metadata: team as author, updated contact email, **Infrastructure** row linking to `infrastructure.md`; architecture / account / pipeline / conventions content moved to `infrastructure.md`; sections renumbered; local connectivity snippet now uses `deploy/scripts/util/validate-aws-cli-identity.py`; document version `1.2.2`.

#### Removed

- `docs/README_old.md` — superseded stub index; history preserved in this changelog.

---

### [1.2.1] — 2026-04-18

#### Added

- `.cursor/README.md` — guide to each top-level folder under **`.cursor/`** (rules, skills, scripts, tools, validation, config, plans, optional placeholders).
- `docs/README.md` — Section **2.4** document index entry linking to **`.cursor/README.md`**; repository layout tree updated for **`.cursor/`**.

---

### [1.2.0] — 2026-04-17

#### Changed

- `docs/README.md` — gold-standard cover page redesign: added version/status/region badges, solution strapline, expanded cover metadata table including architecture diagram link, solution capabilities table, and solution layers table. Bumped document version to `1.2.0`.
- `docs/images/exl-service-logo.png` — refreshed download from Wikimedia Commons canonical source (2,327 × 859 px, public domain PD-textlogo).

---

### [1.1.0] — 2026-04-17

#### Added

- `docs/aws-resource-naming-conventions.md` — comprehensive AWS resource naming patterns, token reference, resource-specific patterns for all primary services (S3, ECR, ECS/EKS, IAM, Secrets Manager, KMS, SQS, RDS, ElastiCache, OpenSearch, Security Groups, VPC Endpoints, CloudWatch, Lambda, Load Balancers, SNS, EventBridge, Terraform state), and the EXLdecision tagging standard.
- Section 2.2 "Standards and conventions" added to the document index to group this and future standards documents.

---

### [1.0.0] — 2026-04-17

#### Added

- `docs/README.md` — master entry point with front-cover branding, numbered headings, document index, architecture summary, getting-started guide, repo layout, and conventions.
- `docs/images/exl-service-logo.png` — EXL Service corporate logo (public domain, Wikimedia Commons).
- `docs/core-infrastructure-workorder-private-aws-services.md` — P0/P1/P2 VPC connectivity work order.
- `docs/workorder-vpc-endpoints-list.md` — full VPC endpoint reference (`us-east-1`).
- `docs/network-connectivity-shared-request-2026-04-16.md` — EXLdecision DEV NLB shared infrastructure request.
- `docs/eks-private-endpoint-check-results.md` — EKS private endpoint probe results.
- `docs/kt-check-endpoint-for-eks-node-attach.md` — EKS node-attach endpoint check procedure.
- `.cursor/rules/architecture.mdc` — agent rules file defining EXLdecision solution architecture principles, component design rules, and the canonical [architecture diagram (Miro)](https://miro.com/app/board/uXjVGnrWh1o=/).
- Architecture diagram link added to `docs/README.md` (summary section and appendix reference links; platform detail later moved to `docs/infrastructure.md` in v1.2.2).

---

## 6. Appendix

### 6.1 Glossary

| Term | Definition |
|---|---|
| EXLdecision | EXL Service Gen-AI analytics platform (this solution; repository `bu-analytics-gen-ai-midas`) |
| Platform overview | [`docs/infrastructure.md`](docs/infrastructure.md) — AWS accounts, VPC, network posture, CI/CD, Well-Architected mapping, IaC conventions |
| RAG | Retrieval-Augmented Generation — a Gen-AI pattern combining vector search with LLM inference |
| NLB | Network Load Balancer |
| ALB | Application Load Balancer |
| TGW | Transit Gateway |
| ECR | Elastic Container Registry |
| EKS | Elastic Kubernetes Service |
| IRSA | IAM Roles for Service Accounts (EKS) |
| VPC endpoint | PrivateLink interface or gateway endpoint providing private AWS API access |
| SSO | AWS IAM Identity Center single sign-on |
| ADR | Architecture Decision Record |

### 6.2 Architecture Decision Records (ADRs)

ADRs document significant technical choices and their rationale. Create individual files as `docs/adr/NNNN-<short-title>.md` and link them here when decisions are recorded.

| ADR | Title | Status | Date |
|---|---|---|---|
| — | _(no ADRs recorded yet)_ | — | — |

### 6.3 Reference links

| Resource | URL |
|---|---|
| **Platform overview (this repo)** | [`docs/infrastructure.md`](docs/infrastructure.md) |
| **EXLdecision architecture diagram (Miro)** | https://miro.com/app/board/uXjVGnrWh1o=/ |
| EXL Service | https://www.exlservice.com |
| EXL Service logo (Wikimedia) | https://commons.wikimedia.org/wiki/File:EXL_Service_logo.png |
| AWS EKS documentation | https://docs.aws.amazon.com/eks/ |
| AWS VPC endpoints (PrivateLink) | https://docs.aws.amazon.com/vpc/latest/privatelink/ |
| Amazon Bedrock | https://docs.aws.amazon.com/bedrock/ |
| Terraform AWS provider | https://registry.terraform.io/providers/hashicorp/aws/latest |
| Keep a Changelog | https://keepachangelog.com/en/1.0.0/ |

---

<div align="center">
  <img src="docs/images/exl-service-logo.png" alt="EXL Service" width="120" /><br/>
  <sub>
    EXLdecision · EXL Service Gen-AI analytics platform<br/>
    BU Analytics · EXL Service &nbsp;|&nbsp; Document version 1.2.3 &nbsp;|&nbsp; 2026-04-18<br/>
    AWS <code>us-east-1</code> · Private VPC · Pipeline-first delivery
  </sub>
</div>

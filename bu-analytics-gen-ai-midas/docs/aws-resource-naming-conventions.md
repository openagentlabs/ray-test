<div align="center">
  <img src="images/exl-service-logo.png" alt="EXL Service" width="260" />
  <h1>MIDAS — AWS Resource Naming Conventions</h1>
  <p><strong>BU Analytics · EXL Service</strong></p>
</div>

---

| Field | Value |
|---|---|
| **Document** | AWS Resource Naming Conventions |
| **Version** | `2.2.0` |
| **Status** | Active |
| **Date** | 2026-04-17 |
| **Author** | Keith Tobin — BU Analytics / Gen-AI MIDAS team |
| **Contact** | `KEITH334747@exlservice.com` |
| **Repository** | `bu-analytics-gen-ai-midas` |
| **Managed by** | Cursor / Pipeline (`deploy/Jenkinsfile_Deploy_App`) |

---

## For the AI Agent — How to Use This Document

> **This section is directed at the Cursor AI agent. Read it in full before creating, naming, or reviewing any AWS resource.**

### What this document is

This is the **single, mandatory source of truth** for every AWS resource name created within the MIDAS platform. It defines the exact naming pattern, format constraints, and a concrete example for every supported resource type. It is not advisory — it is **binding**.

### When it applies

This document applies **every time** any of the following actions occur, without exception:

- A new AWS resource is being created via Terraform (any module under `deploy/ecs-app/modules/` or the root `deploy/ecs-app/`).
- An existing resource name is being reviewed, updated, or referenced in code, documentation, or a PR.
- A new AWS service is being introduced into the MIDAS architecture.
- Any infrastructure question involves resource identification (IAM policies, security group rules, log group paths, secret ARNs, etc.).

### Rules for the agent

1. **Always look up the resource category and row** in Section 4 before generating or accepting a resource name.
2. **Apply the pattern exactly** — substitute the tokens from Section 3 and verify the result matches the example style.
3. **Check the `Max Length` column.** If the generated name would exceed the limit, shorten `{service}` or `{purpose}` and document the abbreviation in the PR or Terraform comment.
4. **Never invent a new pattern.** If a resource type is not yet listed in Section 4, stop and ask the user to confirm the pattern, then add a new row to this table in the same PR.
5. **Flag deviations.** If an existing resource in the codebase does not match this document, raise it as a comment or lint warning — do not silently adopt the non-conforming name.
6. **This document supersedes** any naming pattern suggested by external sources, Stack Overflow, AWS examples, or prior conversation context.

---

## Table of Contents

- [1. General Principles](#1-general-principles)
- [2. Pattern Structure](#2-pattern-structure)
- [3. Token Reference](#3-token-reference)
- [4. Resource Naming Table](#4-resource-naming-table)
  - [4.1 Compute](#41-compute)
  - [4.2 Containers and Orchestration](#42-containers-and-orchestration)
  - [4.3 Storage](#43-storage)
  - [4.4 Database](#44-database)
  - [4.5 Messaging and Eventing](#45-messaging-and-eventing)
  - [4.6 Networking and Content Delivery](#46-networking-and-content-delivery)
  - [4.7 Security, Identity, and Compliance](#47-security-identity-and-compliance)
  - [4.8 Secrets and Configuration](#48-secrets-and-configuration)
  - [4.9 AI and Machine Learning](#49-ai-and-machine-learning)
  - [4.10 Monitoring and Observability](#410-monitoring-and-observability)
  - [4.11 CI/CD and Infrastructure](#411-cicd-and-infrastructure)
  - [4.12 Analytics and Data](#412-analytics-and-data)
  - [4.13 Application Integration](#413-application-integration)
- [5. Naming Rules](#5-naming-rules)
  - [R01 — Use the table as the only source of truth](#r01--use-the-table-as-the-only-source-of-truth)
  - [R02 — Follow the canonical token order](#r02--follow-the-canonical-token-order)
  - [R03 — Always start with the project prefix](#r03--always-start-with-the-project-prefix)
  - [R04 — Always include the environment token](#r04--always-include-the-environment-token)
  - [R05 — Use hyphens as separators](#r05--use-hyphens-as-separators)
  - [R06 — Use lowercase only](#r06--use-lowercase-only)
  - [R07 — Use type-distinguishing suffixes](#r07--use-type-distinguishing-suffixes)
  - [R08 — Keep names short and meaningful](#r08--keep-names-short-and-meaningful)
  - [R09 — Respect max-length limits](#r09--respect-max-length-limits)
  - [R10 — Never hard-code environment or account values](#r10--never-hard-code-environment-or-account-values)
  - [R11 — Treat names as immutable after creation](#r11--treat-names-as-immutable-after-creation)
  - [R12 — Apply the Name tag on every resource](#r12--apply-the-name-tag-on-every-resource)
  - [R13 — Tag-only resources still follow the naming pattern](#r13--tag-only-resources-still-follow-the-naming-pattern)
  - [R14 — Path-style resources use forward slashes](#r14--path-style-resources-use-forward-slashes)
  - [R15 — SQL identifiers use underscores](#r15--sql-identifiers-use-underscores)
  - [R16 — FIFO resources must end in `.fifo`](#r16--fifo-resources-must-end-in-fifo)
  - [R17 — Cross-environment resources omit the env token](#r17--cross-environment-resources-omit-the-env-token)
  - [R18 — Numbered instances use a single-digit suffix](#r18--numbered-instances-use-a-single-digit-suffix)
  - [R19 — Document any abbreviation used to satisfy length limits](#r19--document-any-abbreviation-used-to-satisfy-length-limits)
  - [R20 — New resource types must extend this document before use](#r20--new-resource-types-must-extend-this-document-before-use)
- [6. Tagging Standard](#6-tagging-standard)
- [7. Environment and Account Reference](#7-environment-and-account-reference)
- [8. Change Log](#8-change-log)

---

## 1. General Principles

| # | Principle | Detail |
|---|---|---|
| 1 | **Lowercase only** | All names use lowercase letters (`a–z`), digits (`0–9`), and hyphens (`-`). No uppercase, underscores, dots, or spaces — except where an AWS service explicitly requires it (e.g. SSM path separators `/`, FIFO queue suffix `.fifo`, database identifiers which may require underscores). |
| 2 | **Hyphens as separators** | Tokens are joined with `-`. Use `/` only where path-style naming is the AWS convention (SSM Parameter Store, Secrets Manager, ECR). |
| 3 | **Project prefix first** | All names start with `midas-` so every resource is immediately identified as belonging to this solution. |
| 4 | **Environment second** | `{env}` (`dev` / `uat` / `prod`) is the second token so names sort predictably and cross-environment collisions are impossible. |
| 5 | **Account in S3 names** | S3 bucket names include the AWS account ID (`811391286931`) to guarantee global DNS uniqueness. |
| 6 | **No hard-coded literals** | Names are composed via Terraform interpolation — `var.environment`, `var.aws_account_id`, `var.aws_region`. Never embed literal environment strings inside a module. |
| 7 | **Max-length awareness** | Each row in Section 4 lists the AWS maximum length. If a composed name would exceed it, abbreviate `{service}` or `{purpose}` and document the abbreviation in a Terraform comment. |
| 8 | **No sequential numbers unless required** | Append a numeric suffix (`-1`, `-2`) only for resources that AWS requires to be individually named (e.g. RDS instances, AZ-specific subnets). Do not pad single instances with `-01`. |
| 9 | **Immutability awareness** | Some names cannot be changed after creation (S3 buckets, IAM roles, KMS aliases). Get them right the first time; a rename requires destroy-and-recreate with potential data loss. |
| 10 | **Consistency over creativity** | When in doubt, choose the simpler, shorter name that follows the pattern rather than a creative descriptive name that doesn't. |

---

## 2. Pattern Structure

The canonical MIDAS resource name follows this token order:

```
midas-{env}-{service}-{purpose}-{resource-type-suffix}
```

Not every token is used by every resource — see the per-resource pattern in Section 4. The token order is fixed: when a token is omitted, the remaining tokens close the gap (no double hyphens).

| Position | Token | Always present? |
|---|---|---|
| 1 | `midas` | Yes — fixed project prefix |
| 2 | `{env}` | Yes — except pipeline-wide cross-env resources (e.g. deployer role) |
| 3 | `{service}` | Usually — omit when the resource is shared across all services |
| 4 | `{purpose}` | When needed to distinguish multiple resources of the same type per service |
| 5 | `{resource-type-suffix}` | Where the AWS service type is not self-evident from the name (e.g. `-sg`, `-role`, `-tg`) |

---

## 3. Token Reference

| Token | Description | Allowed values / examples |
|---|---|---|
| `{env}` | Deployment environment | `dev` · `uat` · `prod` |
| `{account}` | AWS account ID — 12 digits, no hyphens | `811391286931` |
| `{region}` | AWS region code | `us-east-1` |
| `{region-short}` | Abbreviated region for length-constrained names | `use1` |
| `{service}` | MIDAS logical service or workload component | `api` · `orchestrator` · `ingest` · `embeddings` · `analytics` · `ui` |
| `{service-name}` | Same as `{service}` but used explicitly in patterns where `{service}` alone would create ambiguity or redundancy (e.g. API Gateway names where the word "api" is also a suffix). | `orchestrator` · `ingest` · `ui` |
| `{purpose}` | Short descriptor for the resource's specific role | `state` · `artifacts` · `logs` · `cache` · `jobs` · `dlq` · `data` |
| `{az}` | Availability zone suffix (last character of AZ name) | `a` · `c` |
| `{index}` | Numeric instance index — only when AWS requires individual names | `1` · `2` |
| `{model}` | Short identifier for an AI/ML model — abbreviate to ≤ 10 chars | `minilm` · `claude3` · `titan` |
| `{source}` | Short identifier for the data source in a pipeline or ETL job | `s3` · `rds` · `kafka` |
| `{target}` | Short identifier for the data target in a pipeline or ETL job | `redshift` · `opensearch` · `s3` |

---

## 4. Resource Naming Table

> **Column guide**
> - **Resource** — AWS resource type and common sub-types.
> - **Description** — what the resource is and its role in MIDAS.
> - **Pattern** — the mandatory naming pattern using tokens from Section 3.
> - **MIDAS Example** — a concrete `dev` environment example.
> - **Max Length** — hard AWS character limit for the name field.
> - **AWS Docs** — placeholder link to the official AWS naming rules page _(update with real URL when confirmed)_.

---

### 4.1 Compute

| Resource | Description | Pattern | MIDAS Example | Max Length | AWS Docs |
|---|---|---|---|---|---|
| **EC2 Instance** | Virtual machine running a MIDAS workload or utility task. EC2 has no resource-name field — the name is set via the `Name` tag. The `-ec2` suffix distinguishes it from other tag-named resources within the same service. | `midas-{env}-{service}-{purpose}-ec2` (Name tag) | `midas-dev-bastion-mgmt-ec2` | 256 (Name tag) | [EC2 Naming](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/Using_Tags.html) |
| **EC2 Auto Scaling Group** | ASG managing a fleet of EC2 instances for a service. | `midas-{env}-{service}-asg` | `midas-dev-api-asg` | 255 | [ASG Docs](https://docs.aws.amazon.com/autoscaling/ec2/userguide/auto-scaling-groups.html) |
| **EC2 Launch Template** | Versioned configuration template for EC2 instances or ASGs. | `midas-{env}-{service}-lt` | `midas-dev-api-lt` | 128 | [Launch Template Docs](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-launch-templates.html) |
| **EC2 Key Pair** | SSH key pair for EC2 instance access (avoid where possible; use SSM Session Manager). | `midas-{env}-{service}-keypair` | `midas-dev-bastion-keypair` | 255 | [Key Pairs Docs](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-key-pairs.html) |
| **Lambda Function** | Serverless function for event-driven logic, triggers, or utility tasks. | `midas-{env}-{service}-{purpose}` | `midas-dev-ingest-trigger` | 64 | [Lambda Naming](https://docs.aws.amazon.com/lambda/latest/dg/configuration-function-common.html) |
| **Lambda Layer** | Shared code / dependency layer attached to Lambda functions. | `midas-{env}-{purpose}-layer` | `midas-dev-common-layer` | 64 | [Lambda Layer Docs](https://docs.aws.amazon.com/lambda/latest/dg/configuration-layers.html) |
| **Lambda Alias** | Pointer to a specific Lambda version (e.g. `live`, `canary`). Aliases are scoped to the parent function — they do not need a project/env prefix because they are never addressed outside their function's ARN. Use a short lowercase purpose word only. | `{purpose}` (no prefix — scoped to function ARN) | `live` · `canary` · `v2` | 64 | [Lambda Alias Docs](https://docs.aws.amazon.com/lambda/latest/dg/configuration-aliases.html) |
| **Elastic Beanstalk Application** | PaaS application container (used only if EB is adopted for MIDAS). The `-eb-app` suffix prevents collision with ECS task definition families that use the same `midas-{env}-{service}` root. | `midas-{env}-{service}-eb-app` | `midas-dev-api-eb-app` | 100 | [EB Docs](https://docs.aws.amazon.com/elasticbeanstalk/latest/dg/applications.html) |
| **Elastic Beanstalk Environment** | Deployed environment within an EB application. | `midas-{env}-{service}-env` | `midas-dev-api-env` | 40 | [EB Environment Docs](https://docs.aws.amazon.com/elasticbeanstalk/latest/dg/using-features.environments.html) |
| **AWS Batch Job Definition** | Definition of a batch compute job (containerised analytics or ML jobs). | `midas-{env}-{service}-{purpose}-job` | `midas-dev-analytics-etl-job` | 128 | [Batch Docs](https://docs.aws.amazon.com/batch/latest/userguide/job_definitions.html) |
| **AWS Batch Job Queue** | Queue that routes batch jobs to a compute environment. | `midas-{env}-{service}-{purpose}-queue` | `midas-dev-analytics-etl-queue` | 128 | [Batch Queue Docs](https://docs.aws.amazon.com/batch/latest/userguide/job_queues.html) |
| **AWS Batch Compute Environment** | Managed or unmanaged compute resources for Batch. | `midas-{env}-{service}-ce` | `midas-dev-analytics-ce` | 128 | [Batch CE Docs](https://docs.aws.amazon.com/batch/latest/userguide/compute_environments.html) |

---

### 4.2 Containers and Orchestration

| Resource | Description | Pattern | MIDAS Example | Max Length | AWS Docs |
|---|---|---|---|---|---|
| **ECR Repository** | Container image registry for a MIDAS service image. Path-style naming. | `midas/{env}/{service}` | `midas/dev/api` | 256 | [ECR Naming](https://docs.aws.amazon.com/AmazonECR/latest/userguide/repository-create.html) |
| **ECS Cluster** | Logical grouping of ECS tasks and services. | `midas-{env}-cluster` | `midas-dev-cluster` | 255 | [ECS Cluster Docs](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/clusters.html) |
| **ECS Task Definition** | Versioned blueprint for an ECS container workload. The `-td` suffix distinguishes the task family name from an ECS service or a CodeDeploy application with the same service name. AWS appends the revision number (`:N`) automatically. | `midas-{env}-{service}-td` | `midas-dev-api-td` | 255 | [ECS Task Definition Docs](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/task_definitions.html) |
| **ECS Service** | Long-running managed ECS workload within a cluster. | `midas-{env}-{service}-svc` | `midas-dev-api-svc` | 255 | [ECS Service Docs](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/ecs_services.html) |
| **EKS Cluster** | Managed Kubernetes control plane for MIDAS workloads. | `midas-{env}-eks` | `midas-dev-eks` | 100 | [EKS Cluster Docs](https://docs.aws.amazon.com/eks/latest/userguide/clusters.html) |
| **EKS Node Group** | Managed worker-node group attached to the EKS cluster. | `midas-{env}-{purpose}-ng` | `midas-dev-general-ng` | 63 | [EKS Node Group Docs](https://docs.aws.amazon.com/eks/latest/userguide/managed-node-groups.html) |
| **EKS Fargate Profile** | Fargate launch profile for serverless EKS pods. | `midas-{env}-{service}-fp` | `midas-dev-api-fp` | 63 | [EKS Fargate Docs](https://docs.aws.amazon.com/eks/latest/userguide/fargate-profile.html) |
| **Kubernetes Namespace** | Logical isolation boundary within EKS. | `midas-{env}` | `midas-dev` | 63 (k8s) | [k8s Namespace Docs](https://kubernetes.io/docs/concepts/overview/working-with-objects/namespaces/) |
| **Kubernetes Deployment** | Declarative spec for a running set of pods. | `midas-{service}` | `midas-api` | 253 (k8s) | [k8s Deployment Docs](https://kubernetes.io/docs/concepts/workloads/controllers/deployment/) |
| **Kubernetes Service** | Stable network endpoint for a Kubernetes workload. | `midas-{service}-svc` | `midas-api-svc` | 253 (k8s) | [k8s Service Docs](https://kubernetes.io/docs/concepts/services-networking/service/) |
| **Kubernetes ConfigMap** | Non-sensitive configuration for pods. | `midas-{service}-config` | `midas-api-config` | 253 (k8s) | [k8s ConfigMap Docs](https://kubernetes.io/docs/concepts/configuration/configmap/) |
| **Kubernetes Secret** | Sensitive configuration injected into pods (backed by Secrets Manager via CSI driver). | `midas-{service}-secret` | `midas-api-secret` | 253 (k8s) | [k8s Secret Docs](https://kubernetes.io/docs/concepts/configuration/secret/) |
| **Kubernetes HPA** | Horizontal Pod Autoscaler for dynamic pod scaling. | `midas-{service}-hpa` | `midas-api-hpa` | 253 (k8s) | [k8s HPA Docs](https://kubernetes.io/docs/tasks/run-application/horizontal-pod-autoscale/) |
| **App Mesh / Service Mesh Virtual Service** | Service Mesh virtual service for traffic routing within EKS. | `midas-{service}.midas-{env}.local` | `midas-api.midas-dev.local` | 255 | [App Mesh Docs](https://docs.aws.amazon.com/app-mesh/latest/userguide/virtual_services.html) |

---

### 4.3 Storage

| Resource | Description | Pattern | MIDAS Example | Max Length | AWS Docs |
|---|---|---|---|---|---|
| **S3 Bucket** | Object storage for data, artifacts, state, logs. Account ID ensures global uniqueness. | `midas-{env}-{account}-{purpose}` | `midas-dev-811391286931-data` | 63 | [S3 Naming Rules](https://docs.aws.amazon.com/AmazonS3/latest/userguide/bucketnamingrules.html) |
| **S3 Bucket — Terraform State** | Dedicated bucket holding Terraform remote state files. | `midas-{env}-{account}-state` | `midas-dev-811391286931-state` | 63 | [S3 Naming Rules](https://docs.aws.amazon.com/AmazonS3/latest/userguide/bucketnamingrules.html) |
| **S3 Bucket — Build Artifacts** | Stores CI/CD pipeline build outputs, Docker layer caches, Helm packages. | `midas-{env}-{account}-artifacts` | `midas-dev-811391286931-artifacts` | 63 | [S3 Naming Rules](https://docs.aws.amazon.com/AmazonS3/latest/userguide/bucketnamingrules.html) |
| **S3 Bucket — Access Logs** | Receives S3 server access logs or ALB/NLB access logs. | `midas-{env}-{account}-logs` | `midas-dev-811391286931-logs` | 63 | [S3 Naming Rules](https://docs.aws.amazon.com/AmazonS3/latest/userguide/bucketnamingrules.html) |
| **S3 Object Key Prefix** | Logical path inside a bucket scoping objects to a service or date partition. | `{service}/{YYYY}/{MM}/{DD}/` | `ingest/2026/04/17/` | — | [S3 Object Key Docs](https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-keys.html) |
| **EFS File System** | Elastic File System for shared persistent storage (EKS persistent volumes). Name tag only — EFS has no name field. | `midas-{env}-{service}-efs` (Name tag) | `midas-dev-models-efs` | 256 (tag) | [EFS Docs](https://docs.aws.amazon.com/efs/latest/ug/gs-step-two-create-efs-resources.html) |
| **EFS Access Point** | Scoped entry point into an EFS file system for a specific workload. | `midas-{env}-{service}-ap` (Name tag) | `midas-dev-api-ap` | 256 (tag) | [EFS Access Point Docs](https://docs.aws.amazon.com/efs/latest/ug/efs-access-points.html) |
| **EBS Volume** | Block storage volume attached to an EC2 instance. Name tag only. | `midas-{env}-{service}-{purpose}-vol` (Name tag) | `midas-dev-api-data-vol` | 256 (tag) | [EBS Docs](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ebs-volumes.html) |
| **EBS Snapshot** | Point-in-time snapshot of an EBS volume. Name tag only. | `midas-{env}-{service}-snap-{YYYYMMDD}` (Name tag) | `midas-dev-api-snap-20260417` | 256 (tag) | [EBS Snapshot Docs](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/EBSSnapshots.html) |
| **Backup Plan (AWS Backup)** | Defines backup frequency and retention policy across resources. | `midas-{env}-{purpose}-backup-plan` | `midas-dev-rds-backup-plan` | 50 | [AWS Backup Docs](https://docs.aws.amazon.com/aws-backup/latest/devguide/creating-a-backup-plan.html) |
| **Backup Vault** | Encrypted container storing AWS Backup recovery points. | `midas-{env}-{purpose}-vault` | `midas-dev-rds-vault` | 50 | [Backup Vault Docs](https://docs.aws.amazon.com/aws-backup/latest/devguide/vaults.html) |

---

### 4.4 Database

| Resource | Description | Pattern | MIDAS Example | Max Length | AWS Docs |
|---|---|---|---|---|---|
| **RDS / Aurora Cluster** | Managed relational database cluster (PostgreSQL or MySQL). | `midas-{env}-{purpose}` | `midas-dev-db` | 63 | [RDS Naming](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_CreateDBInstance.html) |
| **RDS / Aurora Instance** | Individual DB instance within a cluster. Append `-{index}` per instance. | `midas-{env}-{purpose}-{index}` | `midas-dev-db-1` | 63 | [RDS Instance Docs](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_CreateDBInstance.html) |
| **RDS Database Name** | The initial schema / database created inside the instance. Underscores required by SQL identifier rules. | `midas_{env}_{service}` | `midas_dev_api` | 64 | [RDS DB Name Docs](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_CreateDBInstance.html) |
| **RDS Parameter Group** | Custom engine parameter configuration for RDS / Aurora. | `midas-{env}-{purpose}-pg` | `midas-dev-db-pg` | 255 | [Parameter Group Docs](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_WorkingWithParamGroups.html) |
| **RDS Option Group** | Set of engine features for RDS (MySQL/Oracle). | `midas-{env}-{purpose}-og` | `midas-dev-db-og` | 255 | [Option Group Docs](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_WorkingWithOptionGroups.html) |
| **RDS Subnet Group** | List of subnets in which RDS instances may be placed. | `midas-{env}-db-subnet-grp` | `midas-dev-db-subnet-grp` | 255 | [DB Subnet Group Docs](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_VPC.WorkingWithRDSInstanceinaVPC.html) |
| **ElastiCache Replication Group** | Redis replication group for caching or session state. | `midas-{env}-{purpose}` | `midas-dev-cache` | 40 | [ElastiCache Naming](https://docs.aws.amazon.com/AmazonElastiCache/latest/red-ug/Clusters.Create.html) |
| **ElastiCache Cluster (Memcached)** | Memcached cluster for simple distributed caching. | `midas-{env}-{purpose}-mc` | `midas-dev-cache-mc` | 40 | [ElastiCache Memcached Docs](https://docs.aws.amazon.com/AmazonElastiCache/latest/mem-ug/Clusters.Create.html) |
| **ElastiCache Subnet Group** | List of subnets for ElastiCache placement. | `midas-{env}-cache-subnet-grp` | `midas-dev-cache-subnet-grp` | 255 | [ElastiCache Subnet Group Docs](https://docs.aws.amazon.com/AmazonElastiCache/latest/red-ug/SubnetGroups.Creating.html) |
| **OpenSearch Domain** | Managed OpenSearch cluster for vector search or log analytics. | `midas-{env}-{purpose}` | `midas-dev-vectors` | 28 | [OpenSearch Naming](https://docs.aws.amazon.com/opensearch-service/latest/developerguide/createupdatedomains.html) |
| **OpenSearch Index** | Logical partition of data within an OpenSearch domain. | `midas-{env}-{service}-{purpose}` | `midas-dev-api-embeddings` | 255 | [OpenSearch Index Docs](https://opensearch.org/docs/latest/api-reference/index-apis/create-index/) |
| **DynamoDB Table** | Serverless key-value / document store for low-latency lookups. | `midas-{env}-{service}-{purpose}` | `midas-dev-orchestrator-sessions` | 255 | [DynamoDB Naming](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/WorkingWithTables.Basics.html) |
| **DynamoDB Global Table** | A Global Table is not a separate resource — it is the same DynamoDB table enabled for multi-region replication. The table name is identical to the standard DynamoDB Table row above. Replication is configured on the `aws_dynamodb_table` resource via `replica` blocks. Requires ADR before use in MIDAS. | _(same as DynamoDB Table — no separate name)_ | `midas-prod-orchestrator-sessions` | 255 | [DynamoDB Global Table Docs](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/GlobalTables.html) |
| **Redshift Cluster** | Data warehouse cluster for analytical queries. | `midas-{env}-{purpose}` | `midas-dev-warehouse` | 63 | [Redshift Naming](https://docs.aws.amazon.com/redshift/latest/mgmt/working-with-clusters.html) |
| **Redshift Database** | Database within a Redshift cluster. Lowercase. | `midas_{env}_{purpose}` | `midas_dev_analytics` | 127 | [Redshift DB Docs](https://docs.aws.amazon.com/redshift/latest/mgmt/working-with-clusters.html) |
| **Redshift Subnet Group** | Subnets for Redshift cluster placement. | `midas-{env}-redshift-subnet-grp` | `midas-dev-redshift-subnet-grp` | 255 | [Redshift Subnet Group Docs](https://docs.aws.amazon.com/redshift/latest/mgmt/working-with-clusters.html) |

---

### 4.5 Messaging and Eventing

| Resource | Description | Pattern | MIDAS Example | Max Length | AWS Docs |
|---|---|---|---|---|---|
| **SQS Standard Queue** | Durable message queue for decoupling services (at-least-once delivery). | `midas-{env}-{service}-{purpose}` | `midas-dev-ingest-jobs` | 80 | [SQS Naming](https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-queue-message-identifiers.html) |
| **SQS FIFO Queue** | Ordered, exactly-once delivery queue. Must end in `.fifo`. | `midas-{env}-{service}-{purpose}.fifo` | `midas-dev-orchestrator-tasks.fifo` | 80 | [SQS FIFO Docs](https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/FIFO-queues.html) |
| **SQS Dead-Letter Queue** | Receives messages that failed processing after the max receive count. | `midas-{env}-{service}-{purpose}-dlq` | `midas-dev-ingest-jobs-dlq` | 80 | [SQS DLQ Docs](https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-dead-letter-queues.html) |
| **SNS Topic** | Pub/sub topic for fan-out notifications to multiple subscribers. | `midas-{env}-{purpose}` | `midas-dev-ingest-notify` | 256 | [SNS Naming](https://docs.aws.amazon.com/sns/latest/dg/sns-create-topic.html) |
| **SNS FIFO Topic** | Ordered SNS topic for strict sequencing. Must end in `.fifo`. | `midas-{env}-{purpose}.fifo` | `midas-dev-order-events.fifo` | 256 | [SNS FIFO Docs](https://docs.aws.amazon.com/sns/latest/dg/sns-fifo-topics.html) |
| **SNS Subscription** | Named via ARN; AWS does not expose a name field. Use a `Name` tag with `{service}` included so the owning service is traceable alongside the topic name. | Tag: `midas-{env}-{service}-{purpose}-sub` | `midas-dev-ingest-notify-sub` | 256 (tag) | [SNS Subscription Docs](https://docs.aws.amazon.com/sns/latest/dg/sns-create-subscribe-endpoint-to-topic.html) |
| **EventBridge Event Bus** | Custom event bus for MIDAS domain events. | `midas-{env}-{purpose}-bus` | `midas-dev-pipeline-bus` | 256 | [EventBridge Bus Docs](https://docs.aws.amazon.com/eventbridge/latest/userguide/eb-create-event-bus.html) |
| **EventBridge Rule** | Pattern or schedule that routes events to targets. | `midas-{env}-{purpose}-rule` | `midas-dev-analytics-scheduled-rule` | 64 | [EventBridge Rule Docs](https://docs.aws.amazon.com/eventbridge/latest/userguide/eb-create-rule.html) |
| **EventBridge Pipe** | Point-to-point integration between a source and a target with optional filtering / enrichment. | `midas-{env}-{service}-{purpose}-pipe` | `midas-dev-ingest-sqs-pipe` | 64 | [EventBridge Pipe Docs](https://docs.aws.amazon.com/eventbridge/latest/userguide/eb-pipes.html) |
| **Kinesis Data Stream** | Real-time data streaming for high-throughput event ingestion. | `midas-{env}-{service}-{purpose}-stream` | `midas-dev-ingest-events-stream` | 128 | [Kinesis Stream Docs](https://docs.aws.amazon.com/streams/latest/dev/kinesis-using-sdk-java-create-stream.html) |
| **Kinesis Firehose Delivery Stream** | Managed delivery stream from Kinesis to S3, Redshift, or OpenSearch. | `midas-{env}-{service}-{purpose}-firehose` | `midas-dev-ingest-logs-firehose` | 64 | [Firehose Docs](https://docs.aws.amazon.com/firehose/latest/dev/basic-create.html) |
| **Kinesis Analytics Application** | Real-time SQL / Apache Flink application over a Kinesis stream. | `midas-{env}-{service}-{purpose}-kda` | `midas-dev-analytics-events-kda` | 128 | [KDA Docs](https://docs.aws.amazon.com/kinesisanalytics/latest/dev/how-it-works-app.html) |
| **MSK Cluster (Kafka)** | Managed Kafka cluster for high-throughput streaming. | `midas-{env}-{purpose}-kafka` | `midas-dev-events-kafka` | 64 | [MSK Docs](https://docs.aws.amazon.com/msk/latest/developerguide/msk-create-cluster.html) |
| **Step Functions State Machine** | Orchestration workflow coordinating Lambda, ECS, or Bedrock calls. | `midas-{env}-{service}-{purpose}-sm` | `midas-dev-orchestrator-inference-sm` | 80 | [Step Functions Docs](https://docs.aws.amazon.com/step-functions/latest/dg/concepts-amazon-states-language.html) |

---

### 4.6 Networking and Content Delivery

| Resource | Description | Pattern | MIDAS Example | Max Length | AWS Docs |
|---|---|---|---|---|---|
| **VPC** | Virtual Private Cloud — the private network boundary for MIDAS. (Centrally managed; Name tag only.) | `midas-{env}-vpc` (Name tag) | `midas-dev-vpc` | 256 (tag) | [VPC Docs](https://docs.aws.amazon.com/vpc/latest/userguide/working-with-vpcs.html) |
| **Subnet** | IP address subdivision within the VPC, scoped to an AZ and tier. (Centrally managed; Name tag only.) | `midas-{env}-{purpose}-{az}` (Name tag) | `midas-dev-private-a` | 256 (tag) | [Subnet Docs](https://docs.aws.amazon.com/vpc/latest/userguide/configure-subnets.html) |
| **Route Table** | Defines routing rules for subnets. (Centrally managed; Name tag only.) | `midas-{env}-{purpose}-rt` (Name tag) | `midas-dev-private-rt` | 256 (tag) | [Route Table Docs](https://docs.aws.amazon.com/vpc/latest/userguide/VPC_Route_Tables.html) |
| **Internet Gateway** | Provides internet egress — NOT used in MIDAS (private VPC). Included for completeness; requires architecture exception. | `midas-{env}-igw` (Name tag) | _Not used — architecture exception required_ | 256 (tag) | [IGW Docs](https://docs.aws.amazon.com/vpc/latest/userguide/VPC_Internet_Gateway.html) |
| **NAT Gateway** | Outbound-only internet access for private subnets — NOT used in MIDAS (TGW egress). Requires architecture exception. | `midas-{env}-{az}-nat` (Name tag) | _Not used — architecture exception required_ | 256 (tag) | [NAT GW Docs](https://docs.aws.amazon.com/vpc/latest/userguide/vpc-nat-gateway.html) |
| **Transit Gateway Attachment** | Connects the MIDAS VPC to the corporate Transit Gateway. (Centrally managed; Name tag only.) | `midas-{env}-tgw-att` (Name tag) | `midas-dev-tgw-att` | 256 (tag) | [TGW Docs](https://docs.aws.amazon.com/vpc/latest/tgw/tgw-vpc-attachments.html) |
| **VPC Endpoint — Interface** | PrivateLink interface endpoint for AWS services (ECR, Secrets Manager, Bedrock, etc.). | `midas-{env}-{aws-service}-ep` | `midas-dev-secretsmanager-ep` | 256 (tag) | [VPC Endpoint Docs](https://docs.aws.amazon.com/vpc/latest/privatelink/create-interface-endpoint.html) |
| **VPC Endpoint — Gateway** | Gateway endpoint for S3 or DynamoDB (no ENI, route-table based). | `midas-{env}-{aws-service}-ep` | `midas-dev-s3-ep` | 256 (tag) | [Gateway Endpoint Docs](https://docs.aws.amazon.com/vpc/latest/privatelink/gateway-endpoints.html) |
| **Security Group** | Stateful firewall rules for a resource tier. Always include a meaningful `description`. | `midas-{env}-{service}-sg` | `midas-dev-api-sg` | 255 | [Security Group Docs](https://docs.aws.amazon.com/vpc/latest/userguide/security-groups.html) |
| **Network ACL** | Stateless subnet-level traffic filter. (Centrally managed; Name tag only.) | `midas-{env}-{purpose}-nacl` (Name tag) | `midas-dev-private-nacl` | 256 (tag) | [NACL Docs](https://docs.aws.amazon.com/vpc/latest/userguide/vpc-network-acls.html) |
| **Application Load Balancer (ALB)** | Layer-7 HTTP/HTTPS load balancer for internal service traffic. | `midas-{env}-alb` | `midas-dev-alb` | 32 | [ALB Naming](https://docs.aws.amazon.com/elasticloadbalancing/latest/application/create-application-load-balancer.html) |
| **Network Load Balancer (NLB)** | Layer-4 TCP/TLS load balancer for high-throughput internal traffic. | `midas-{env}-nlb` | `midas-dev-nlb` | 32 | [NLB Naming](https://docs.aws.amazon.com/elasticloadbalancing/latest/network/create-network-load-balancer.html) |
| **ALB / NLB Target Group** | Group of backend targets registered behind a load balancer listener. | `midas-{env}-{service}-tg` | `midas-dev-api-tg` | 32 | [Target Group Docs](https://docs.aws.amazon.com/elasticloadbalancing/latest/application/load-balancer-target-groups.html) |
| **ALB Listener Rule** | Routing condition on an ALB listener. Named via tags. | Tag: `midas-{env}-{service}-{purpose}-rule` | `midas-dev-api-v1-rule` | 256 (tag) | [Listener Rule Docs](https://docs.aws.amazon.com/elasticloadbalancing/latest/application/listener-update-rules.html) |
| **Route 53 Hosted Zone** | DNS zone for internal MIDAS service discovery. | `midas-{env}.internal` (zone name) | `midas-dev.internal` | 1024 | [Route 53 Docs](https://docs.aws.amazon.com/Route53/latest/DeveloperGuide/hosted-zones-working-with.html) |
| **Route 53 Record** | DNS record within a hosted zone. | `{service}.midas-{env}.internal` | `api.midas-dev.internal` | 1024 | [Route 53 Record Docs](https://docs.aws.amazon.com/Route53/latest/DeveloperGuide/rrsets-working-with.html) |
| **CloudFront Distribution** | Content delivery — not used in MIDAS private VPC by default; requires architecture exception. | `midas-{env}-{purpose}-cf` (Description field) | _Requires architecture exception_ | 128 (description) | [CloudFront Docs](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/distribution-working-with.html) |
| **API Gateway REST API** | Managed HTTP API gateway for MIDAS service APIs. Use `{service-name}` (the actual service name, not the generic `api` token) to avoid the redundant `midas-dev-api-rest-api` pattern. | `midas-{env}-{service-name}-rest-api` | `midas-dev-orchestrator-rest-api` | 1024 | [API GW Docs](https://docs.aws.amazon.com/apigateway/latest/developerguide/rest-api-create.html) |
| **API Gateway Stage** | Deployed stage of an API Gateway (corresponds to env). | `{env}` | `dev` · `prod` | 128 | [API GW Stage Docs](https://docs.aws.amazon.com/apigateway/latest/developerguide/set-up-stages.html) |
| **API Gateway HTTP API** | Lightweight HTTP API (preferred over REST API for new integrations). Use `{service-name}` explicitly — not the generic `api` token — to avoid redundant names. | `midas-{env}-{service-name}-http-api` | `midas-dev-orchestrator-http-api` | 1024 | [HTTP API Docs](https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api.html) |
| **Global Accelerator** | Anycast global traffic accelerator — not used in MIDAS private VPC. Requires architecture exception. | `midas-{env}-{purpose}-ga` | _Requires architecture exception_ | 255 | [Global Accelerator Docs](https://docs.aws.amazon.com/global-accelerator/latest/dg/getting-started.html) |

---

### 4.7 Security, Identity, and Compliance

| Resource | Description | Pattern | MIDAS Example | Max Length | AWS Docs |
|---|---|---|---|---|---|
| **IAM Role** | Identity that grants AWS API permissions to a service, workload, or pipeline. | `midas-{env}-{service}-role` | `midas-dev-api-role` | 64 | [IAM Role Docs](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_create.html) |
| **IAM Role — EKS Node** | IAM role assumed by EKS worker nodes. | `midas-{env}-eks-node-role` | `midas-dev-eks-node-role` | 64 | [EKS Node Role Docs](https://docs.aws.amazon.com/eks/latest/userguide/create-node-role.html) |
| **IAM Role — IRSA (EKS)** | IAM role for a Kubernetes service account (IRSA / Pod Identity). | `midas-{env}-{service}-irsa-role` | `midas-dev-orchestrator-irsa-role` | 64 | [IRSA Docs](https://docs.aws.amazon.com/eks/latest/userguide/iam-roles-for-service-accounts.html) |
| **IAM Role — ECS Task Execution** | Role used by the ECS agent to pull images and write logs. | `midas-{env}-{service}-exec-role` | `midas-dev-api-exec-role` | 64 | [ECS Task Execution Role](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/task_execution_IAM_role.html) |
| **IAM Role — ECS Task** | Role assumed by the running container to access AWS APIs. | `midas-{env}-{service}-task-role` | `midas-dev-api-task-role` | 64 | [ECS Task Role Docs](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/task-iam-roles.html) |
| **IAM Role — Deployer (Pipeline)** | Cross-environment role assumed by Jenkins for Terraform deploys. No env token — controlled by pipeline parameter. | `midas-deployer` | `midas-deployer` | 64 | [IAM Role Docs](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_create.html) |
| **IAM Managed Policy** | Customer-managed policy attached to roles. | `midas-{env}-{service}-policy` | `midas-dev-api-policy` | 128 | [IAM Policy Docs](https://docs.aws.amazon.com/IAM/latest/UserGuide/access_policies_create.html) |
| **IAM Managed Policy — Deployer** | Numbered policy files for the deployer role (max 10 attachments). | `midas-deployer-policy-{NNN}` | `midas-deployer-policy-001` | 128 | [IAM Policy Docs](https://docs.aws.amazon.com/IAM/latest/UserGuide/access_policies_create.html) |
| **IAM Instance Profile** | Wraps an IAM role for attachment to EC2 instances. | `midas-{env}-{service}-profile` | `midas-dev-api-profile` | 128 | [Instance Profile Docs](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_use_switch-role-ec2_instance-profiles.html) |
| **IAM OIDC Provider** | OIDC identity provider for EKS IRSA. Identified by issuer URL; tag with Name. | Tag: `midas-{env}-eks-oidc` | `midas-dev-eks-oidc` | 256 (tag) | [OIDC Provider Docs](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_providers_create_oidc.html) |
| **KMS Key** | Customer-managed encryption key. Identified by key ID / ARN; described via alias. | _(no name field — use alias)_ | _See KMS Alias below_ | — | [KMS Key Docs](https://docs.aws.amazon.com/kms/latest/developerguide/create-keys.html) |
| **KMS Alias** | Human-readable pointer to a KMS key. Must start with `alias/`. | `alias/midas-{env}-{purpose}` | `alias/midas-dev-s3` | 256 | [KMS Alias Docs](https://docs.aws.amazon.com/kms/latest/developerguide/kms-alias.html) |
| **ACM Certificate** | TLS certificate managed by AWS Certificate Manager. Named via domain; tag with `Name`. | Tag: `midas-{env}-{service}-cert` | `midas-dev-api-cert` | 256 (tag) | [ACM Docs](https://docs.aws.amazon.com/acm/latest/userguide/gs-acm-request-public.html) |
| **WAF Web ACL** | Web Application Firewall ACL protecting ALB or API Gateway. | `midas-{env}-{purpose}-waf` | `midas-dev-api-waf` | 128 | [WAF Docs](https://docs.aws.amazon.com/waf/latest/developerguide/waf-chapter.html) |
| **WAF IP Set** | Named set of IP addresses referenced in WAF rules. | `midas-{env}-{purpose}-ipset` | `midas-dev-corp-ipset` | 128 | [WAF IP Set Docs](https://docs.aws.amazon.com/waf/latest/developerguide/waf-ip-set-managing.html) |
| **GuardDuty Detector** | Threat detection service. One per account/region; tagged only. | Tag: `midas-{env}-guardduty` | `midas-dev-guardduty` | 256 (tag) | [GuardDuty Docs](https://docs.aws.amazon.com/guardduty/latest/ug/create-detector.html) |
| **Security Hub** | Aggregated security findings. One per account/region; tagged only. | Tag: `midas-{env}-securityhub` | `midas-dev-securityhub` | 256 (tag) | [Security Hub Docs](https://docs.aws.amazon.com/securityhub/latest/userguide/securityhub-enable.html) |
| **Config Rule** | AWS Config rule for compliance evaluation. | `midas-{env}-{purpose}-config-rule` | `midas-dev-s3-public-block-config-rule` | 128 | [Config Rule Docs](https://docs.aws.amazon.com/config/latest/developerguide/evaluate-config_develop-rules.html) |

---

### 4.8 Secrets and Configuration

| Resource | Description | Pattern | MIDAS Example | Max Length | AWS Docs |
|---|---|---|---|---|---|
| **Secrets Manager Secret** | Encrypted secret (credentials, API keys, tokens) with optional rotation. Path-style naming. | `midas/{env}/{service}/{secret-name}` | `midas/dev/api/db-password` | 512 | [Secrets Manager Docs](https://docs.aws.amazon.com/secretsmanager/latest/userguide/create_secret.html) |
| **SSM Parameter — String** | Non-sensitive configuration value stored in Parameter Store. | `/midas/{env}/{service}/{parameter-name}` | `/midas/dev/api/db-host` | 1024 | [SSM Parameter Docs](https://docs.aws.amazon.com/systems-manager/latest/userguide/sysman-paramstore-su-create.html) |
| **SSM Parameter — SecureString** | Sensitive value stored encrypted in Parameter Store (KMS-backed). Prefer Secrets Manager for rotation. | `/midas/{env}/{service}/{secret-name}` | `/midas/dev/api/db-password` | 1024 | [SSM SecureString Docs](https://docs.aws.amazon.com/systems-manager/latest/userguide/sysman-paramstore-su-create.html) |
| **AppConfig Application** | AWS AppConfig application container for runtime feature flags and config. The `-appconfig` suffix prevents collision with ECS task definition families and CodeDeploy applications that share the `midas-{env}-{service}` root. | `midas-{env}-{service}-appconfig` | `midas-dev-api-appconfig` | 2048 | [AppConfig Docs](https://docs.aws.amazon.com/appconfig/latest/userguide/appconfig-creating-application.html) |
| **AppConfig Environment** | Deployment target within an AppConfig application. | `{env}` | `dev` · `prod` | 2048 | [AppConfig Environment Docs](https://docs.aws.amazon.com/appconfig/latest/userguide/appconfig-creating-environment.html) |
| **AppConfig Configuration Profile** | Named config profile (e.g. feature flags) within an AppConfig application. The `{env}` token is intentionally omitted here because the profile exists inside an AppConfig Application resource that is already environment-scoped (e.g. `midas-dev-api-appconfig`). | `midas-{service}-{purpose}-profile` | `midas-api-flags-profile` | 2048 | [AppConfig Profile Docs](https://docs.aws.amazon.com/appconfig/latest/userguide/appconfig-creating-configuration-and-profile.html) |

---

### 4.9 AI and Machine Learning

| Resource | Description | Pattern | MIDAS Example | Max Length | AWS Docs |
|---|---|---|---|---|---|
| **Bedrock Model Invocation (no named resource)** | Amazon Bedrock foundation model calls have no named AWS resource — models are referenced by their model ID (e.g. `anthropic.claude-3-5-sonnet-20241022-v2:0`). The naming convention here is for the **CloudWatch log group** used to capture Bedrock invocation logs for this service. See Section 4.10 for the full log group pattern. | CW log group: `/midas/{env}/{service}/bedrock` | `/midas/dev/orchestrator/bedrock` | 512 (log group) | [Bedrock Docs](https://docs.aws.amazon.com/bedrock/latest/userguide/what-is-bedrock.html) |
| **Bedrock Knowledge Base** | Managed RAG knowledge base backed by an S3 data source and a vector store. | `midas-{env}-{service}-{purpose}-kb` | `midas-dev-orchestrator-docs-kb` | 100 | [Bedrock KB Docs](https://docs.aws.amazon.com/bedrock/latest/userguide/knowledge-base.html) |
| **Bedrock Agent** | Agentic orchestration component that calls tools and knowledge bases. | `midas-{env}-{service}-{purpose}-agent` | `midas-dev-orchestrator-main-agent` | 100 | [Bedrock Agent Docs](https://docs.aws.amazon.com/bedrock/latest/userguide/agents.html) |
| **Bedrock Agent Alias** | Versioned pointer to a Bedrock Agent (analogous to a Lambda alias). Include `{service}` so the alias is unambiguous when multiple agents exist in the same environment. | `midas-{env}-{service}-{purpose}-alias` | `midas-dev-orchestrator-live-alias` | 100 | [Bedrock Agent Alias Docs](https://docs.aws.amazon.com/bedrock/latest/userguide/agents-alias.html) |
| **SageMaker Domain** | Studio / JupyterLab environment for ML development. | `midas-{env}-sagemaker` | `midas-dev-sagemaker` | 63 | [SageMaker Domain Docs](https://docs.aws.amazon.com/sagemaker/latest/dg/gs-studio-onboard.html) |
| **SageMaker Endpoint** | Deployed real-time inference endpoint for a trained model. | `midas-{env}-{service}-{model}-ep` | `midas-dev-embeddings-minilm-ep` | 63 | [SageMaker Endpoint Docs](https://docs.aws.amazon.com/sagemaker/latest/dg/realtime-endpoints.html) |
| **SageMaker Endpoint Config** | Configuration for a SageMaker inference endpoint. Note: the full pattern can reach 40+ characters with real model names — keep `{model}` to ≤ 10 characters (abbreviate model names, e.g. `minilm`, `claude3`) to stay safely under the 63-char limit. | `midas-{env}-{service}-{model}-ep-cfg` | `midas-dev-embeddings-minilm-ep-cfg` | 63 | [SageMaker Endpoint Config Docs](https://docs.aws.amazon.com/sagemaker/latest/dg/realtime-endpoints.html) |
| **SageMaker Model** | Registered model artefact referencing a container and S3 data. | `midas-{env}-{service}-{model}` | `midas-dev-embeddings-minilm` | 63 | [SageMaker Model Docs](https://docs.aws.amazon.com/sagemaker/latest/dg/realtime-endpoints.html) |
| **SageMaker Pipeline** | ML workflow pipeline (data prep → train → evaluate → register). | `midas-{env}-{service}-{purpose}-pipeline` | `midas-dev-embeddings-train-pipeline` | 256 | [SageMaker Pipeline Docs](https://docs.aws.amazon.com/sagemaker/latest/dg/pipelines.html) |
| **SageMaker Feature Group** | Named group of ML features stored in the Feature Store. | `midas-{env}-{service}-{purpose}-fg` | `midas-dev-ingest-user-fg` | 64 | [Feature Store Docs](https://docs.aws.amazon.com/sagemaker/latest/dg/feature-store.html) |
| **Comprehend Custom Classifier** | Custom text classification model (e.g. intent detection). | `midas-{env}-{purpose}-classifier` | `midas-dev-intent-classifier` | 63 | [Comprehend Docs](https://docs.aws.amazon.com/comprehend/latest/dg/how-document-classification.html) |

---

### 4.10 Monitoring and Observability

| Resource | Description | Pattern | MIDAS Example | Max Length | AWS Docs |
|---|---|---|---|---|---|
| **CloudWatch Log Group** | Container for log streams from a service or AWS resource. | `/midas/{env}/{service}` | `/midas/dev/api` | 512 | [Log Group Docs](https://docs.aws.amazon.com/AmazonCloudWatch/latest/logs/Working-with-log-groups-and-streams.html) |
| **CloudWatch Log Group — ECS** | Log group scoped to ECS task logging. | `/midas/{env}/ecs/{service}` | `/midas/dev/ecs/api` | 512 | [ECS Logging Docs](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/using_awslogs.html) |
| **CloudWatch Log Group — Lambda** | Log group auto-created by Lambda; must be pre-created in Terraform to control retention. | `/aws/lambda/midas-{env}-{service}-{purpose}` | `/aws/lambda/midas-dev-ingest-trigger` | 512 | [Lambda Logging Docs](https://docs.aws.amazon.com/lambda/latest/dg/monitoring-cloudwatchlogs.html) |
| **CloudWatch Metric Alarm** | Alert on a CloudWatch metric threshold breach. | `midas-{env}-{service}-{metric}-alarm` | `midas-dev-api-cpu-alarm` | 255 | [CloudWatch Alarm Docs](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/AlarmThatSendsEmail.html) |
| **CloudWatch Composite Alarm** | Alarm composed of multiple metric alarms (AND / OR logic). | `midas-{env}-{service}-composite-alarm` | `midas-dev-api-composite-alarm` | 255 | [Composite Alarm Docs](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/Create_Composite_Alarm.html) |
| **CloudWatch Dashboard** | Visual dashboard for operational metrics. The `-dash` suffix prevents collision with the identical `midas-{env}-{service}` pattern used by ECS Task Definitions and X-Ray Groups. | `midas-{env}-{service}-dash` | `midas-dev-api-dash` | 255 | [Dashboard Docs](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/CloudWatch_Dashboards.html) |
| **CloudWatch Log Metric Filter** | Extracts metric data from log events. Name prefixed with service. | `midas-{env}-{service}-{metric}-mf` | `midas-dev-api-error-rate-mf` | 512 | [Metric Filter Docs](https://docs.aws.amazon.com/AmazonCloudWatch/latest/logs/FilterAndPatternSyntax.html) |
| **CloudWatch Insights Query (saved)** | Saved Log Insights query for operational troubleshooting. | `midas-{env}-{service}-{purpose}-query` | `midas-dev-api-p99-latency-query` | 255 | [Insights Docs](https://docs.aws.amazon.com/AmazonCloudWatch/latest/logs/CWL_AnalyzeLogData_RunSampleQuery.html) |
| **X-Ray Group** | Traces sampling group for a service or request type. The `-xray-grp` suffix prevents collision with other `midas-{env}-{service}` resources (ECS task definitions, dashboards). X-Ray group names are case-insensitive and max 32 chars — keep `{service}` ≤ 12 chars. | `midas-{env}-{service}-xray-grp` | `midas-dev-api-xray-grp` | 32 | [X-Ray Group Docs](https://docs.aws.amazon.com/xray/latest/devguide/xray-console-groups.html) |
| **X-Ray Sampling Rule** | Custom sampling rate for X-Ray trace collection. | `midas-{env}-{service}-sample` | `midas-dev-api-sample` | 32 | [X-Ray Sampling Docs](https://docs.aws.amazon.com/xray/latest/devguide/xray-console-sampling.html) |
| **SNS Topic — Alerting** | Dedicated SNS topic for CloudWatch alarm notifications. | `midas-{env}-alerts` | `midas-dev-alerts` | 256 | [SNS Naming](https://docs.aws.amazon.com/sns/latest/dg/sns-create-topic.html) |

---

### 4.11 CI/CD and Infrastructure

| Resource | Description | Pattern | MIDAS Example | Max Length | AWS Docs |
|---|---|---|---|---|---|
| **S3 Terraform State Key** | Object key path within the state bucket for a Terraform root module. The key is a path-style string, not an AWS resource name — it has no AWS character limit beyond the S3 object key maximum. | `{env}/midas/{component}.tfstate` | `dev/midas/ecs-app.tfstate` | 1024 (S3 key) | [S3 Object Key Docs](https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-keys.html) |
| **DynamoDB Table — Terraform Lock** | State locking table to prevent concurrent Terraform applies. | `midas-{env}-tf-lock` | `midas-dev-tf-lock` | 255 | [DynamoDB Naming](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/WorkingWithTables.Basics.html) |
| **CodePipeline Pipeline** | AWS CodePipeline for CI/CD automation (if adopted alongside Jenkins). | `midas-{env}-{service}-pipeline` | `midas-dev-api-pipeline` | 100 | [CodePipeline Docs](https://docs.aws.amazon.com/codepipeline/latest/userguide/pipelines-create.html) |
| **CodeBuild Project** | Managed build environment within a pipeline stage. | `midas-{env}-{service}-{purpose}-build` | `midas-dev-api-docker-build` | 255 | [CodeBuild Docs](https://docs.aws.amazon.com/codebuild/latest/userguide/create-project.html) |
| **CodeDeploy Application** | CodeDeploy application container for deployment groups. The `-cd-app` suffix prevents collision with ECS task definition families that use the same `midas-{env}-{service}` root. | `midas-{env}-{service}-cd-app` | `midas-dev-api-cd-app` | 100 | [CodeDeploy Docs](https://docs.aws.amazon.com/codedeploy/latest/userguide/applications-create.html) |
| **CodeDeploy Deployment Group** | Target set for a CodeDeploy deployment. | `midas-{env}-{service}-dg` | `midas-dev-api-dg` | 100 | [Deployment Group Docs](https://docs.aws.amazon.com/codedeploy/latest/userguide/deployment-groups-create.html) |
| **CloudFormation Stack** | IaC stack (used for resources not managed by Terraform in this project). | `midas-{env}-{purpose}-stack` | `midas-dev-network-stack` | 128 | [CloudFormation Stack Docs](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/stacks.html) |
| **CloudFormation StackSet** | Multi-account or multi-region CloudFormation deployment. The `{env}` token is intentionally omitted because StackSets target multiple accounts/environments simultaneously — their scope is cross-environment by design. | `midas-{purpose}-stackset` | `midas-vpc-endpoints-stackset` | 128 | [StackSet Docs](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/what-is-cfnstacksets.html) |

---

### 4.12 Analytics and Data

| Resource | Description | Pattern | MIDAS Example | Max Length | AWS Docs |
|---|---|---|---|---|---|
| **Glue Database** | Glue Data Catalog database grouping related tables. | `midas_{env}_{purpose}` (underscores required) | `midas_dev_raw` | 255 | [Glue DB Docs](https://docs.aws.amazon.com/glue/latest/dg/define-database.html) |
| **Glue Table** | Schema definition for a dataset in the Glue Data Catalog. | `midas_{env}_{service}_{dataset}` (underscores) | `midas_dev_ingest_events` | 255 | [Glue Table Docs](https://docs.aws.amazon.com/glue/latest/dg/tables-described.html) |
| **Glue Crawler** | Discovers and catalogues schema from S3 or other data sources. | `midas-{env}-{service}-{purpose}-crawler` | `midas-dev-ingest-events-crawler` | 255 | [Glue Crawler Docs](https://docs.aws.amazon.com/glue/latest/dg/add-crawler.html) |
| **Glue ETL Job** | Serverless Spark or Python ETL job for data transformation. | `midas-{env}-{source}-to-{target}-job` | `midas-dev-s3-to-redshift-job` | 255 | [Glue Job Docs](https://docs.aws.amazon.com/glue/latest/dg/author-job.html) |
| **Glue Connection** | Connection configuration to a data store (JDBC, Kafka, etc.). | `midas-{env}-{purpose}-conn` | `midas-dev-rds-conn` | 255 | [Glue Connection Docs](https://docs.aws.amazon.com/glue/latest/dg/connection-defining.html) |
| **Glue Workflow** | Multi-step Glue orchestration workflow. | `midas-{env}-{purpose}-wf` | `midas-dev-ingest-wf` | 255 | [Glue Workflow Docs](https://docs.aws.amazon.com/glue/latest/dg/workflows_overview.html) |
| **Athena Workgroup** | Isolated query execution environment with cost controls. | `midas-{env}-{purpose}-wg` | `midas-dev-analytics-wg` | 128 | [Athena Workgroup Docs](https://docs.aws.amazon.com/athena/latest/ug/user-created-workgroups.html) |
| **Athena Named Query** | Saved Athena SQL query for operational reuse. | `midas-{env}-{service}-{purpose}-query` | `midas-dev-ingest-daily-summary-query` | 128 | [Athena Named Query Docs](https://docs.aws.amazon.com/athena/latest/ug/saved-queries.html) |
| **QuickSight Data Source** | Named connection from QuickSight to a data store. | `midas-{env}-{purpose}-qs-ds` | `midas-dev-redshift-qs-ds` | 128 | [QuickSight DS Docs](https://docs.aws.amazon.com/quicksight/latest/user/create-a-data-source.html) |
| **QuickSight Dataset** | Prepared dataset used in QuickSight analyses and dashboards. | `midas-{env}-{service}-{purpose}-qs` | `midas-dev-analytics-kpi-qs` | 128 | [QuickSight Dataset Docs](https://docs.aws.amazon.com/quicksight/latest/user/create-a-dataset.html) |

---

### 4.13 Application Integration

| Resource | Description | Pattern | MIDAS Example | Max Length | AWS Docs |
|---|---|---|---|---|---|
| **AWS AppSync API** | Managed GraphQL API layer (if adopted in MIDAS). The `65536` limit is the AppSync API **description** field — the API **name** limit is 65 characters. Keep the name well under 65 chars. | `midas-{env}-{service-name}-graphql` | `midas-dev-orchestrator-graphql` | 65 (name) | [AppSync Docs](https://docs.aws.amazon.com/appsync/latest/devguide/creating-a-graphql-api.html) |
| **Cognito User Pool** | User directory for authentication (internal tooling or partner access). | `midas-{env}-{purpose}-users` | `midas-dev-admin-users` | 128 | [Cognito User Pool Docs](https://docs.aws.amazon.com/cognito/latest/developerguide/cognito-user-identity-pools.html) |
| **Cognito User Pool Client** | App client within a Cognito User Pool. | `midas-{env}-{service}-client` | `midas-dev-api-client` | 128 | [Cognito App Client Docs](https://docs.aws.amazon.com/cognito/latest/developerguide/user-pool-settings-client-apps.html) |
| **Cognito Identity Pool** | Federated identity pool for vending temporary AWS credentials. | `midas-{env}-{purpose}-id-pool` | `midas-dev-admin-id-pool` | 128 | [Cognito Identity Pool Docs](https://docs.aws.amazon.com/cognito/latest/developerguide/identity-pools.html) |
| **Service Catalog Portfolio** | Curated collection of approved MIDAS infrastructure products. | `midas-{env}-{purpose}-portfolio` | `midas-dev-infra-portfolio` | 100 | [Service Catalog Docs](https://docs.aws.amazon.com/servicecatalog/latest/adminguide/portfoliomgmt-create.html) |
| **Service Catalog Product** | Single approved infrastructure template in a Service Catalog portfolio. | `midas-{env}-{purpose}-product` | `midas-dev-eks-product` | 100 | [Service Catalog Product Docs](https://docs.aws.amazon.com/servicecatalog/latest/adminguide/productmgmt-create.html) |

---

## 5. Naming Rules

> These rules are **mandatory**. They apply to every AWS resource created within the MIDAS platform, without exception. Each rule references the relevant section of this document and is written to be unambiguous for both engineers and AI agents.

---

### R01 — Use the table as the only source of truth

**Rule:** Before naming any AWS resource, locate the resource type in the [Section 4 table](#4-resource-naming-table). The `Pattern` column in that row defines the name. Do not use a name derived from memory, external examples, or convention alone.

**Applies to:** Every resource, always.

**Reference:** [Section 4 — Resource Naming Table](#4-resource-naming-table)

**Correct:**
```
# ECS Service — look up row, apply pattern midas-{env}-{service}-svc
resource "aws_ecs_service" "api" {
  name = "midas-dev-api-svc"
}
```
**Incorrect:**
```
# Invented without consulting the table
name = "dev-api-service"
```

---

### R02 — Follow the canonical token order

**Rule:** Token order within a name is fixed as: `midas` → `{env}` → `{service}` → `{purpose}` → `{resource-type-suffix}`. Do not swap, skip, or reorder tokens unless the specific row in Section 4 explicitly states otherwise.

**Reference:** [Section 2 — Pattern Structure](#2-pattern-structure)

**Correct:** `midas-dev-ingest-jobs-dlq` (`midas` · `dev` · `ingest` · `jobs` · `dlq`)

**Incorrect:** `dev-midas-dlq-ingest-jobs` (reordered) · `ingest-dev-jobs-dlq` (missing prefix)

---

### R03 — Always start with the project prefix

**Rule:** Every AWS resource name **must** begin with `midas-`. This makes MIDAS resources immediately identifiable in any AWS Console view, CLI output, billing report, or CloudTrail log. The only exception is when an AWS service does not support a name field at all (tag-only resources), in which case the `Name` tag must still follow this rule (see [R12](#r12--apply-the-name-tag-on-every-resource)).

**Reference:** [Section 1, Principle 3](#1-general-principles)

**Correct:** `midas-dev-api-sg`

**Incorrect:** `api-sg` · `dev-api-sg` · `bu-midas-dev-api-sg`

---

### R04 — Always include the environment token

**Rule:** The `{env}` token (`dev`, `uat`, or `prod`) must appear as the second token in every name. It prevents naming collisions across environments sharing account `811391286931`. The only exceptions are resources that are explicitly cross-environment by design (the deployer IAM role, CloudFormation StackSets) — these exceptions are documented in the [Section 4 table](#4-resource-naming-table) in the Pattern column.

**Reference:** [Section 1, Principle 4](#1-general-principles) · [Section 6 — Environment and Account Reference](#7-environment-and-account-reference)

**Correct:** `midas-dev-api-sg` · `midas-uat-api-sg` · `midas-prod-api-sg`

**Incorrect:** `midas-api-sg` (missing env) · `midas-development-api-sg` (full word, not the token value)

---

### R05 — Use hyphens as separators

**Rule:** Tokens within a name are always joined with a hyphen (`-`). Never use underscores, dots, spaces, or camelCase as word separators in a resource name — unless an AWS service explicitly requires it (see [R15](#r15--sql-identifiers-use-underscores) for SQL and [R16](#r16--fifo-resources-must-end-in-fifo) for FIFO). There must be no leading, trailing, or consecutive hyphens.

**Reference:** [Section 1, Principle 2](#1-general-principles)

**Correct:** `midas-dev-api-sg`

**Incorrect:** `midas_dev_api_sg` · `midas.dev.api.sg` · `midas-dev--api-sg` · `midas-dev-api-sg-`

---

### R06 — Use lowercase only

**Rule:** All characters in a resource name must be lowercase (`a–z`), digits (`0–9`), or hyphens (`-`). Mixed case and uppercase are forbidden, even where AWS technically permits them (e.g. IAM, CloudWatch), because inconsistent case makes CLI filtering, Terraform state keys, and log searches unreliable. Exceptions covered by [R15](#r15--sql-identifiers-use-underscores) and [R16](#r16--fifo-resources-must-end-in-fifo) still use lowercase.

**Reference:** [Section 1, Principle 1](#1-general-principles)

**Correct:** `midas-dev-api-role`

**Incorrect:** `Midas-Dev-Api-Role` · `MIDAS_DEV_API_ROLE` · `midasDevApiRole`

---

### R07 — Use type-distinguishing suffixes

**Rule:** When multiple AWS resource types share the same `midas-{env}-{service}` root (e.g. ECS Task Definition, CodeDeploy Application, AppConfig Application, CloudWatch Dashboard, X-Ray Group), the pattern for each type adds a short **resource-type suffix** to make the resource type self-evident from the name alone. Always apply the suffix shown in the Section 4 Pattern column — do not omit it to save characters. If the suffix would cause a max-length breach, abbreviate `{service}` first, not the suffix.

**Reference:** [Section 2 — Pattern Structure](#2-pattern-structure), position 5 (`{resource-type-suffix}`)

| Type | Suffix | Example |
|---|---|---|
| ECS Task Definition | `-td` | `midas-dev-api-td` |
| ECS Service | `-svc` | `midas-dev-api-svc` |
| IAM Role | `-role` | `midas-dev-api-role` |
| Security Group | `-sg` | `midas-dev-api-sg` |
| Auto Scaling Group | `-asg` | `midas-dev-api-asg` |
| Target Group | `-tg` | `midas-dev-api-tg` |
| Dead-Letter Queue | `-dlq` | `midas-dev-ingest-jobs-dlq` |
| CloudWatch Dashboard | `-dash` | `midas-dev-api-dash` |
| X-Ray Group | `-xray-grp` | `midas-dev-api-xray-grp` |
| KMS Alias | `alias/` prefix | `alias/midas-dev-s3` |

For the full list, see the `Pattern` column in [Section 4](#4-resource-naming-table).

---

### R08 — Keep names short and meaningful

**Rule:** Names must be concise but self-describing. Use the shortest token value that unambiguously identifies the service or purpose — single words preferred (e.g. `api`, `ingest`, `cache`). Do not embed redundant context that is already encoded elsewhere in the name (e.g. do not add the region to a name when the provider is already region-fixed at `us-east-1`). Do not use abbreviations that are not listed in [Section 3](#3-token-reference) unless they are documented per [R19](#r19--document-any-abbreviation-used-to-satisfy-length-limits).

**Reference:** [Section 3 — Token Reference](#3-token-reference)

**Correct:** `midas-dev-ingest-jobs-dlq`

**Incorrect:** `midas-dev-us-east-1-ingestion-service-jobs-dead-letter-queue` (verbose, includes region already implied)

---

### R09 — Respect max-length limits

**Rule:** Every row in [Section 4](#4-resource-naming-table) shows the AWS hard character limit for that resource's name field. Before finalising a name, count the characters of the composed name and verify it is within the limit. If the name would exceed the limit, shorten `{service}` or `{purpose}` (in that priority order). Do not shorten the type suffix or the `midas-` prefix. Document any shortening per [R19](#r19--document-any-abbreviation-used-to-satisfy-length-limits).

**Services with tight limits to watch:**

| Resource | Limit | Risk |
|---|---|---|
| OpenSearch Domain | 28 chars | Very tight — max 3–4 chars for `{purpose}` |
| X-Ray Group / Sampling Rule | 32 chars | Tight — `{service}` must be ≤ 12 chars |
| ALB / NLB name | 32 chars | Tight — single service token only |
| ALB / NLB Target Group | 32 chars | Tight |
| EKS Node Group / Fargate Profile | 63 chars | Moderate |
| SageMaker resources | 63 chars | Moderate — abbreviate model names |
| Lambda Function | 64 chars | Moderate |
| IAM Role | 64 chars | Moderate |

**Reference:** [Section 4 — Resource Naming Table](#4-resource-naming-table), Max Length column

---

### R10 — Never hard-code environment or account values

**Rule:** Resource names must be composed using Terraform variable interpolation, not string literals. This ensures the same module works identically across `dev`, `uat`, and `prod` without modification.

**Reference:** [Section 1, Principle 6](#1-general-principles)

**Correct:**
```hcl
name = "midas-${var.environment}-${var.service_name}-sg"
```
**Incorrect:**
```hcl
name = "midas-dev-api-sg"   # hard-coded env
```

---

### R11 — Treat names as immutable after creation

**Rule:** For resources whose names cannot be changed without destroying and recreating them (S3 buckets, IAM roles and policies, KMS aliases, RDS cluster identifiers, ElastiCache replication groups, OpenSearch domains), treat the name as permanent from the moment the resource is first provisioned. Verify the name in a `terraform plan` review before applying. If a name must change, plan for data migration and a maintenance window.

**Immutable resources include (non-exhaustive):**

| Resource | Consequence of rename |
|---|---|
| S3 Bucket | Destroy + recreate; data migration required |
| IAM Role / Policy | All trust policies and attachments must be updated |
| KMS Alias | Key access via old alias name breaks immediately |
| RDS Cluster Identifier | Snapshot restore or rename via AWS support |
| ElastiCache Replication Group | Destroy + recreate; cache warm-up required |
| OpenSearch Domain | Destroy + recreate; index migration required |
| EKS Cluster | Destroy + recreate; all workloads disrupted |

**Reference:** [Section 1, Principle 9](#1-general-principles)

---

### R12 — Apply the Name tag on every resource

**Rule:** Every AWS resource must have a `Name` tag whose value exactly matches the name defined by the Section 4 pattern for that resource. For resources that have no native name field (VPC, Subnet, Route Table, EFS, EBS, etc.), the `Name` tag is the only way to identify the resource in the console and CLI — it is mandatory, not optional.

**Reference:** [Section 6 — Tagging Standard](#6-tagging-standard)

**Correct:**
```hcl
resource "aws_security_group" "api" {
  name = "midas-${var.environment}-api-sg"
  tags = {
    Name = "midas-${var.environment}-api-sg"
  }
}
```
**Incorrect:**
```hcl
resource "aws_vpc_endpoint" "secretsmanager" {
  # No Name tag — resource is invisible in console without it
}
```

---

### R13 — Tag-only resources still follow the naming pattern

**Rule:** Some AWS resources have no native `name` field and are identified only by their `Name` tag (VPC, Subnet, Route Table, Network ACL, Transit Gateway Attachment, EFS File System, EBS Volume, EBS Snapshot, VPC Endpoint). These resources must still follow the Section 4 Pattern column for their type. The fact that the name lives in a tag does not make the naming convention optional.

**Pattern column annotation:** rows where the name is tag-only are marked with `(Name tag)` in the Pattern column of [Section 4](#4-resource-naming-table).

**Reference:** [Section 4 — Resource Naming Table](#4-resource-naming-table)

---

### R14 — Path-style resources use forward slashes

**Rule:** Resources that use a path-style hierarchy instead of a flat name (AWS Secrets Manager, SSM Parameter Store, ECR repositories, S3 object key prefixes) use forward slashes (`/`) as the hierarchy separator, not hyphens. The path still begins with `midas` (or `/midas` for SSM) and includes the `{env}` token as the first path segment after the prefix. Do not mix hyphens and slashes within the path.

**Reference:** [Section 1, Principle 2](#1-general-principles) · [Section 4.2](#42-containers-and-orchestration) · [Section 4.8](#48-secrets-and-configuration)

| Resource | Pattern | Example |
|---|---|---|
| Secrets Manager Secret | `midas/{env}/{service}/{secret-name}` | `midas/dev/api/db-password` |
| SSM Parameter | `/midas/{env}/{service}/{param-name}` | `/midas/dev/api/db-host` |
| ECR Repository | `midas/{env}/{service}` | `midas/dev/api` |
| S3 Object Key Prefix | `{service}/{YYYY}/{MM}/{DD}/` | `ingest/2026/04/17/` |

---

### R15 — SQL identifiers use underscores

**Rule:** When an AWS service stores names that are used directly as SQL or Hive identifiers (RDS database names, Redshift database names, Glue database names, Glue table names), use underscores (`_`) instead of hyphens because SQL identifiers cannot contain hyphens. All other naming rules (lowercase, project prefix, environment token) still apply.

**Reference:** [Section 4.4 — Database](#44-database) · [Section 4.12 — Analytics and Data](#412-analytics-and-data)

| Resource | Pattern | Example |
|---|---|---|
| RDS / Aurora database name | `midas_{env}_{service}` | `midas_dev_api` |
| Redshift database | `midas_{env}_{purpose}` | `midas_dev_analytics` |
| Glue database | `midas_{env}_{purpose}` | `midas_dev_raw` |
| Glue table | `midas_{env}_{service}_{dataset}` | `midas_dev_ingest_events` |

---

### R16 — FIFO resources must end in `.fifo`

**Rule:** AWS requires SQS FIFO queues and SNS FIFO topics to have names ending in `.fifo`. This suffix is mandatory and enforced by AWS at creation time. It counts toward the character limit (80 chars for SQS, 256 for SNS). Ensure the composed name including `.fifo` stays within the limit.

**Reference:** [Section 4.5 — Messaging and Eventing](#45-messaging-and-eventing)

| Resource | Pattern | Example |
|---|---|---|
| SQS FIFO Queue | `midas-{env}-{service}-{purpose}.fifo` | `midas-dev-orchestrator-tasks.fifo` |
| SNS FIFO Topic | `midas-{env}-{purpose}.fifo` | `midas-dev-order-events.fifo` |

---

### R17 — Cross-environment resources omit the env token

**Rule:** A small number of resources are shared across all environments and have no per-environment variant. These resources omit the `{env}` token from their name. This exception is **only** permitted when the Section 4 Pattern column explicitly shows the token omitted and includes an explanatory note. Never omit `{env}` on your own initiative.

**Current approved exceptions:**

| Resource | Name | Reason |
|---|---|---|
| IAM Role — Deployer | `midas-deployer` | Single role assumed by Jenkins for all environments; environment is a pipeline parameter |
| IAM Managed Policy — Deployer | `midas-deployer-policy-{NNN}` | Attached to the deployer role above |
| CloudFormation StackSet | `midas-{purpose}-stackset` | Targets multiple accounts/environments simultaneously by design |

**Reference:** [Section 4.7 — Security, Identity, and Compliance](#47-security-identity-and-compliance) · [Section 4.11 — CI/CD and Infrastructure](#411-cicd-and-infrastructure)

---

### R18 — Numbered instances use a single-digit suffix

**Rule:** When AWS requires individually named instances within a logical group (e.g. RDS instances within a cluster, AZ-specific subnets), append a numeric suffix starting at `1`. Use a single digit — do not zero-pad (use `-1`, not `-01`). Apply this only when the Section 4 Pattern column includes `{index}`. Do not add numbers to resources that are singleton by design.

**Reference:** [Section 3 — Token Reference](#3-token-reference), `{index}` token

**Correct:** `midas-dev-db-1` · `midas-dev-db-2`

**Incorrect:** `midas-dev-db-01` · `midas-dev-db-001` · `midas-dev-db-instance1`

---

### R19 — Document any abbreviation used to satisfy length limits

**Rule:** When a `{service}` or `{purpose}` token must be abbreviated to keep a name within its max-length limit (see [R09](#r09--respect-max-length-limits)), the abbreviation must be documented in:
1. A Terraform inline comment on the resource block, and
2. The PR description for the change.

This prevents the next engineer from seeing a cryptic abbreviation and "fixing" it back to the full word, breaking the name constraint.

**Reference:** [Section 1, Principle 7](#1-general-principles)

**Example:**
```hcl
# OpenSearch domain: max 28 chars.
# "vec" abbreviates "vectors" to fit: midas-dev-vec = 13 chars (safe).
resource "aws_opensearch_domain" "vectors" {
  domain_name = "midas-${var.environment}-vec"
}
```

---

### R20 — New resource types must extend this document before use

**Rule:** If a Terraform resource type is not listed in [Section 4](#4-resource-naming-table), it must **not** be provisioned until a new row has been added to the appropriate category table in this document. The new row must follow the same column format (Resource · Description · Pattern · MIDAS Example · Max Length · AWS Docs) and must be reviewed and merged in the same PR as the Terraform code that introduces the resource. Do not name a new resource type ad hoc and add it to the document retroactively.

**Reference:** [For the AI Agent — Rules for the agent](#for-the-ai-agent--how-to-use-this-document), Rule 4

---

## 6. Tagging Standard

All AWS resources **must** carry the following tags. Apply the baseline via a `default_tags` block in the Terraform AWS provider configuration; add resource-specific tags in each resource's own `tags` block. The `Name` tag value must match the naming pattern from [Section 4](#4-resource-naming-table) exactly — see [Rule R12](#r12--apply-the-name-tag-on-every-resource).

| Tag Key | Required | Description | Example Value |
|---|---|---|---|
| `Name` | **Yes** | Human-readable resource name — must exactly match the naming convention name used for the resource. | `midas-dev-api-sg` |
| `Environment` | **Yes** | Deployment environment. | `dev` · `uat` · `prod` |
| `Project` | **Yes** | Solution identifier. | `midas` |
| `ManagedBy` | **Yes** | Who or what created and manages this resource. | `terraform` |
| `Owner` | **Yes** | Team or individual responsible for the resource. | `bu-analytics` |
| `CostCenter` | **Yes** (if known) | Cost allocation code for billing reports. | `bu-analytics-midas` |
| `Service` | Recommended | MIDAS logical service that owns the resource. | `api` · `orchestrator` |
| `Version` | Recommended | Application or module version deployed. | `1.3.0` |
| `DataClassification` | For data stores | Sensitivity level of data held in the resource. | `internal` · `confidential` |

**Terraform `default_tags` provider block:**

```hcl
provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Environment = var.environment
      Project     = "midas"
      ManagedBy   = "terraform"
      Owner       = "bu-analytics"
    }
  }
}
```

> `Name` and `Service` are resource-specific and must be set per-resource in the `tags` block. `default_tags` cannot set `Name` because every resource has a different name.

---

## 7. Environment and Account Reference

| `{env}` Value | Description | AWS Account ID | Terraform `environment` Variable |
|---|---|---|---|
| `dev` | Development — pipeline-deployed, shared by the dev team. | `811391286931` | `dev` |
| `uat` | User Acceptance Testing — pre-production validation. | `811391286931` | `uat` |
| `prod` | Production — live customer-facing workloads. | `811391286931` | `prod` |

> All three environments currently share account `811391286931`. The `{env}` token in every resource name is the primary guard against cross-environment collisions. Never omit it — see [Rule R04](#r04--always-include-the-environment-token).

---

## 8. Change Log

### [2.2.0] — 2026-04-17

#### Added

- **Section 5 — Naming Rules** — 20 explicit, numbered rules (R01–R20) that define how every AWS resource must be named, each with a statement, rationale, cross-references to the relevant section of this document, and correct/incorrect examples where applicable. Rules cover: table-first lookup (R01), token order (R02), project prefix (R03), environment token (R04), hyphen separators (R05), lowercase (R06), type-distinguishing suffixes (R07), name brevity (R08), max-length compliance (R09), no hard-coded literals (R10), immutability (R11), Name tag (R12), tag-only resources (R13), path-style resources (R14), SQL underscore identifiers (R15), FIFO suffix (R16), cross-environment resources (R17), numbered instances (R18), abbreviation documentation (R19), and new resource type process (R20).
- Existing sections renumbered: Tagging Standard → Section 6, Environment Reference → Section 7, Change Log → Section 8.
- Cross-references from Tagging Standard and Environment Reference sections added to point at the relevant naming rules.

### [2.1.0] — 2026-04-17

#### Fixed (document validation pass)

- **EC2 Instance** — added `(Name tag)` annotation to Pattern column and `-ec2` suffix to distinguish from other tag-named resources; corrected example.
- **ECS Task Definition** — added `-td` suffix to prevent pattern collision with Elastic Beanstalk Application, CodeDeploy Application, AppConfig Application, and CloudWatch Dashboard (all previously shared `midas-{env}-{service}`).
- **Elastic Beanstalk Application** — added `-eb-app` suffix for same collision reason.
- **CodeDeploy Application** — added `-cd-app` suffix for same collision reason.
- **AppConfig Application** — added `-appconfig` suffix for same collision reason.
- **CloudWatch Dashboard** — added `-dash` suffix to remove collision with ECS Task Definition / X-Ray Group patterns.
- **X-Ray Group** — added `-xray-grp` suffix; added note about 32-char limit requiring short `{service}` names (≤ 12 chars).
- **API Gateway REST API** — renamed token to `{service-name}` and fixed example to remove the redundant `midas-dev-api-api` pattern.
- **API Gateway HTTP API** — same fix as REST API.
- **AWS AppSync API** — corrected Max Length from `65536 (description)` (wrong field) to `65 (name)`; updated example to use `{service-name}`.
- **Bedrock Agent Alias** — added `{service}` token back into pattern to disambiguate aliases across multiple agents.
- **Bedrock Model Invocation** — clarified the row: the convention here names the CloudWatch log group, not a Bedrock resource; cross-referenced Section 4.10.
- **SNS Subscription** — added `{service}` token to the tag pattern so the owning service is traceable.
- **DynamoDB Global Table** — clarified that this is not a separately named resource; Global Tables share the DynamoDB Table name.
- **CloudFormation StackSet** — added explicit note explaining why `{env}` is omitted (cross-environment by design).
- **AppConfig Configuration Profile** — added explicit note explaining why `{env}` is omitted (profile is scoped inside an env-specific Application).
- **SageMaker Endpoint Config** — shortened suffix from `ep-config` to `ep-cfg`; added note to keep `{model}` ≤ 10 chars to avoid hitting the 63-char limit.
- **S3 Terraform State Key** — corrected Max Length from `—` to `1024 (S3 key)`.
- **Lambda Alias** — added explanation that no prefix is needed because aliases are scoped to the parent function ARN.
- **Section 3 Token Reference** — added `{service-name}`, `{model}`, `{source}`, and `{target}` tokens (required by API Gateway and Glue ETL Job patterns).

### [2.0.0] — 2026-04-17

#### Changed

- Complete document rewrite. Replaced per-section free-text patterns with a unified, category-grouped table format covering all primary AWS resource types used in or relevant to the MIDAS platform.
- Added mandatory AI-agent preamble (top of document) defining when and how to use this document.
- Expanded from 18 resource entries to 100+ entries across 13 categories.
- Added `Description`, `Max Length`, and `AWS Docs` columns to every resource row.
- Added new categories: Compute extensions (Batch, EB), AI/ML (Bedrock, SageMaker), Analytics (Glue, Athena, QuickSight), Application Integration (AppSync, Cognito), and full Kubernetes sub-resources.
- Tagging standard updated with `Service`, `Version`, and `DataClassification` tags.
- Pattern structure section added (Section 2) explaining token order and omission rules.

### [1.0.0] — 2026-04-17

#### Added

- Initial naming convention document (18 resource types, free-text per-section format).

---

<div align="center">
  <sub>
    MIDAS · BU Analytics · EXL Service &nbsp;|&nbsp; Document version 2.2.0 &nbsp;|&nbsp; 2026-04-17
  </sub>
</div>

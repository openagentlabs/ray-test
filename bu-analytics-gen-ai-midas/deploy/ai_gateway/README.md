# MIDAS AI Gateway deployment (`deploy/ai_gateway/`)

This folder contains **MIDAS-owned** deployment configuration for the AI Gateway component.
The upstream AI Gateway code lives under `ai_gateway/` (a Git submodule). **This folder is the
only place where MIDAS-specific values, Jenkinsfiles, and overrides should live**, with the
exception of JFrog elimination edits which (per Q15.2 + Q20.1) live on the
`midas/jfrog-elimination` branch of the MIDAS fork of the AI Gateway repo.

For the full decision history and prerequisites see
[`.cursor/scratch/sop-capture-2026-04-19_1529.md`](../../.cursor/scratch/sop-capture-2026-04-19_1529.md).

## Folder layout

```
deploy/ai_gateway/
├── README.md                        ← this file
├── image-bootstrap/                 ← ORD2: image sources + Dockerfiles for from-source builds
│   ├── images.yaml                  ← single source of truth for image tags + sources
│   └── docker/                      ← Dockerfiles for components built from source
│       └── control-api/             ← MIDAS-built Control API image (replaces JFrog version)
├── terraform/                       ← Terragrunt environment for the AI Gateway TF module
│   └── environment/
│       └── dev/
│           └── terragrunt.hcl       ← MIDAS-account inputs (account 811391286931)
├── helm/                            ← MIDAS values overrides for each Helm chart
│   ├── clickhouse/values-midas-dev.yaml
│   ├── langfuse/values-midas-dev.yaml
│   ├── litellm/values-midas-dev.yaml
│   └── control-api/values-midas-dev.yaml
├── jenkinsfiles/                    ← 7 ORD pipelines, one Jenkinsfile per stage
│   ├── Jenkinsfile_ORD1_terraform
│   ├── Jenkinsfile_ORD2_image_bootstrap
│   ├── Jenkinsfile_ORD3_clickhouse
│   ├── Jenkinsfile_ORD4_langfuse
│   ├── Jenkinsfile_ORD5_litellm
│   ├── Jenkinsfile_ORD6_control_api
│   └── Jenkinsfile_ORD7_orchestrator
└── jenkins-job-templates/           ← config.xml templates used by jenkins_tools.py create-job
    └── pipeline-job-template.xml
```

## Naming convention

All AWS resources created by these pipelines use the prefix **`midas-aigtw-dev-*`**.
See SOP §19.5 for the full list (ECR repos, RDS, Redis, ALB, NLB, KMS, Secrets, etc.).

## Pipelines (Jenkins folder `exlerate/exlerate-solutions/MIDAS/`)

The seven pipelines run in strict ORD order. ORD7 is the orchestrator that calls ORD1→ORD6.

| ORD | Pipeline name | Purpose |
|---|---|---|
| 1 | `midas-ai-gateway-tf-deploy-ORD1` | Terraform deploy of all dedicated AWS infra |
| 2 | `midas-ai-gateway-image-bootstrap-ORD2` | Pull images from public registries (via Netskope) and build Control API from source; push all to MIDAS ECR |
| 3 | `midas-ai-gateway-clickhouse-ORD3` | Helm install ClickHouse (Langfuse dependency) |
| 4 | `midas-ai-gateway-langfuse-ORD4` | Helm install Langfuse |
| 5 | `midas-ai-gateway-litellm-ORD5` | Helm install LiteLLM |
| 6 | `midas-ai-gateway-control-api-ORD6` | Helm install Control API |
| 7 | `midas-ai-gateway-orchestrator-ORD7` | Calls ORD1→ORD6 in sequence with input gates between stages |

## Hard rules

1. **Do NOT edit anything under `ai_gateway/`** in this repo — that's the read-only submodule
   pinned at the upstream MIDAS-fork branch. JFrog elimination edits live on the fork's
   `midas/jfrog-elimination` branch (Q15.2 + Q20.1). See `.cursor/rules/ai_gateway.mdc`.
2. **Do NOT create Jenkins pipelines outside the `exlerate/exlerate-solutions/MIDAS/` folder.**
3. **Do NOT touch any other existing Jenkins pipeline.** Scope is limited to the seven new ORD pipelines.
4. **Do NOT push the MIDAS fork branch to upstream.** The upstream remote has push DISABLED.
5. **Do NOT create new VPC, subnets, or jumpbox.** These are explicitly shared per Step 19.

## Prerequisites tracker

See SOP §18.1 (M-1 through M-16). Pipelines will refuse to run until P-prereqs are green.

## Manual ops

- Pulling new upstream changes into the fork: see `.cursor/scratch/readme.md` §6 (the upstream-pull
  workflow, applied on the fork instead of upstream).
- kubectl access to the new EKS cluster: use `deploy/scripts/util/aws-ssm-kubectl-proxy.py`
  via the shared jumpbox `i-04231b2a8a4d98b63`.

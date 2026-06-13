# Upstream blockers — values that CANNOT be overridden from the MIDAS overlay

Account: `811391286931` (`ns-ai-midas-dev-use1-dev`) · region `us-east-1` · cluster `midas-eks-aigtw-dev`.

The MIDAS overlay (`deploy/ai_gateway/`) overrides every upstream-pointing value that is exposed
as a Terraform `variable` or Helm value. The items below are **hardcoded inside the upstream
submodule** (`ai_gateway/…`) and have no input/value indirection. They can only be fixed by
editing the submodule on a MIDAS-owned fork branch (M-16) and re-pinning the submodule URL
in `.gitmodules` (Step 21).

These do not block `terragrunt plan`/`apply` *now* in every case — some only break at apply time
(e.g. data source lookups) or only produce cosmetically wrong resource names (e.g. SG name).

| # | File | Line | Hardcoded upstream identifier | Impact in MIDAS account | Fix on the fork |
|---|------|------|------------------------------|-------------------------|-----------------|
| B-1 | `ai_gateway/infra/terraform/modules/acm.tf` | 2-22 | `data "aws_acm_certificate" "exlerate-ai-gateway-cert" { domain = "exlerate-ai-gateway-${env}.exlservice.com" }` and `resource "aws_acm_certificate" "exlerate-ai-gateway-cert-dev-stable"` | **HARD FAIL** at `terragrunt apply`: the ACM cert does not exist in MIDAS account 811391286931. Domain is upstream-owned. | Replace with `data "aws_acm_certificate" "midas_aigtw_cert" { domain = "midas-aigtw.${var.environment}.exlservice.com" }` and rename the dev-stable resource similarly. Updates required in `litellm_app_deps.tf:75` and `langfuse_app_deps.tf:129` to match. Pre-req: corporate cert request M-7. |
| B-2 | `ai_gateway/infra/terraform/modules/litellm_app_deps.tf` | 75 | `data.aws_acm_certificate.exlerate-ai-gateway-cert[0].arn` | Same as B-1 (cert lookup chained). | Rename data-source reference to match B-1 fix. |
| B-3 | `ai_gateway/infra/terraform/modules/langfuse_app_deps.tf` | 129 | `aws_acm_certificate.exlerate-ai-gateway-cert-dev-stable[0]` and `data.aws_acm_certificate.exlerate-ai-gateway-cert[0]` | Same as B-1 (cert lookup chained). | Rename both references to match B-1 fix. |
| B-4 | `ai_gateway/infra/terraform/modules/security_groups.tf` | 137 | SG `name = "exlerate-litellm-alb-sg-${var.eks_cluster_name}"` | Resource is created with name `exlerate-litellm-alb-sg-midas-eks-aigtw-dev` — works, but mis-prefixed (looks like a leak from upstream). | Change to `midas-aigtw-litellm-alb-sg-${var.eks_cluster_name}` (or, better, take an input variable for the prefix). |
| B-5 | `ai_gateway/infra/terraform/modules/alb.tf` | 195 | ALB controller image: `ucjfrog.exlservice.com/exlerate-docker-platform-internal-dev-local/eks/aws-load-balancer-controller` | **HARD FAIL** at runtime if Netskope blocks JFrog (Q15.1 = `approve_hybrid` mandates ZERO JFrog at runtime). Pulling controller image from corporate JFrog conflicts with our policy. | Change to `${var.aws_load_balancer_controller_image_repo}` (default `811391286931.dkr.ecr.us-east-1.amazonaws.com/midas-aigtw-dev-aws-load-balancer-controller`) and add the variable. Pre-req: ORD2 must mirror controller image to MIDAS ECR. |
| B-6 | `ai_gateway/helm/langfuse/values.yaml` | 32-44 | S3 bucket names: `exlerate-dev-langfuse-data-bucket`, `exlerate-dev-langfuse-media-bucket` | Overridable from Helm overlay (already done in `deploy/ai_gateway/helm/langfuse/values-midas-dev.yaml`). NOT a fork blocker, but logged for completeness. | n/a (overlay handles it). |
| B-7 | `ai_gateway/helm/langfuse/values.yaml` | 193 | Cognito issuer URL: `https://cognito-idp.us-east-1.amazonaws.com/us-east-1_u5hcfpBrh` | Overridable via `langfuse.additionalEnv[AUTH_CUSTOM_ISSUER]` — done in our overlay (now sourced from `midas-aigtw-dev-langfuse-cognito` Secret). NOT a fork blocker. | n/a (overlay handles it). |
| B-8 | `ai_gateway/helm/langfuse/values.yaml` | 111, 195 | Hostname `exlerate-ai-observability-dev.exlservice.com` and label "EXLerate SSO" | Overridable in our overlay (`langfuse.nextauth.url`, `AUTH_CUSTOM_NAME`). NOT a fork blocker. | n/a (overlay handles it). |

## Status decision matrix

| Status | What it means |
|---|---|
| **HARD BLOCKER** | Pipeline cannot reach `apply` (or runtime) without the fork fix. Items: B-1, B-2, B-3, B-5. |
| **COSMETIC** | Pipeline succeeds but a resource has the wrong prefix; can be renamed during the fork rollout. Items: B-4. |
| **HANDLED BY OVERLAY** | Already overridden in `deploy/ai_gateway/`; logged here for traceability. Items: B-6, B-7, B-8. |

## Sequencing

1. **Now (without the fork)**: `terragrunt init` + `plan` works. The HARD BLOCKERS surface during `terragrunt plan` only if the data source is reached during planning (ACM data sources are evaluated at plan time → B-1/B-2/B-3 will fail at `plan`).
2. **Before any `terragrunt apply` against MIDAS**: complete the M-16 fork (`midas/jfrog-elimination` branch on the MIDAS-owned mirror) with B-1, B-2, B-3, B-5 fixes, then update `.gitmodules` to point at the fork and run `git submodule sync && git submodule update --init --recursive`.

## How to find new upstream leaks later

```bash
rg --no-heading -n \
   '927215579862|634655358372|vpc-0f1fb60f70d0c3d61|10\.95\.96\.0|exlerate-(ai-gateway|dev|litellm)|uc-tf-state-exlerate|ami-0ac16465f699316de|jfrog\.io|jfrog\.exlservice\.com' \
   ai_gateway deploy/ai_gateway
```
Anything new under `deploy/ai_gateway/` is a real bug in our overlay (must be fixed there).
Anything new under `ai_gateway/` is either already in this list or needs to be added.

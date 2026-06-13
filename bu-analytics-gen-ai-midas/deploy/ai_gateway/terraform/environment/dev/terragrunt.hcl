# MIDAS-owned Terragrunt env for the AI Gateway dev deployment.
#
# This file is the MIDAS overlay of `ai_gateway/infra/terraform/environment/dev/terragrunt.hcl`.
# It substitutes ALL upstream values with MIDAS-account values per Step 19 (isolation policy).
#
# - Account:    811391286931 (ns-ai-midas-dev-use1-dev)
# - Region:     us-east-1
# - VPC:        vpc-0c4d673f3e95a93eb (SHARED — only allowed shared resource)
# - Subnets:    per SOP §17.1 (SHARED)
# - Cluster:    midas-eks-aigtw-dev (DEDICATED, NEW)
# - State:      s3://midas-aigtw-dev-us-east-1-terraform-811391286931 (M-11)

terraform {
  # MIDAS in-tree fork: copy of upstream `ai_gateway/infra/terraform/modules/` into
  # `deploy/ai_gateway/terraform/modules-midas/` with these MIDAS-only patches applied:
  #   - version.tf: drop empty `backend "s3" {}` (Terragrunt v0.48 generates one and would conflict)
  #   - acm.tf: gate upstream cert data sources to count=0; cert ARN now passed via
  #             `var.midas_acm_certificate_arn` (corporate cert request M-7 fulfils this)
  #   - alb.tf: replace JFrog ALB-controller image with MIDAS ECR; gate jfrog-regcred imagePullSecret
  #             behind `var.use_jfrog_image_pull_secret` (defaults false)
  #   - litellm_app_deps.tf, langfuse_app_deps.tf: replaced data.aws_acm_certificate references
  # Upstream `ai_gateway/` submodule is read-only and remains untouched (per user mandate).
  # Re-mirror upstream changes by re-running `cp -R ai_gateway/infra/terraform/modules/. \
  #   deploy/ai_gateway/terraform/modules-midas/` and re-applying the patches.
  source = "${get_repo_root()}/deploy/ai_gateway/terraform/modules-midas"
}

remote_state {
  backend = "s3"
  # ROOT-CAUSE NOTE (build #11):
  # Earlier we removed the empty `backend "s3" {}` block from modules-midas/version.tf
  # to fix a "Duplicate backend configuration" error. That removal silently broke
  # remote state — Terragrunt's `-backend-config=...` CLI flag injection only WORKS
  # when an existing backend block is present in the .tf files; without it, terraform
  # init falls back to the LOCAL backend, state is written to the Jenkins workspace,
  # and is wiped between builds (= why AWS had resources but s3://.../aigtw/ was empty).
  # Fix: explicitly generate a complete `backend.tf` from Terragrunt — this is the
  # idiomatic Terragrunt v0.48 pattern and removes the dependency on the upstream
  # version.tf shape.
  generate = {
    path      = "backend.tf"
    if_exists = "overwrite_terragrunt"
  }
  config = {
    # TODO(isolation): swap to midas-aigtw-dev-us-east-1-terraform-811391286931 once M-11 lands.
    # The existing midas-dev TF state bucket is reused with a unique 'aigtw/' key prefix for
    # bootstrap so we can prove the chain end-to-end; state stored in `aigtw/...` cannot
    # collide with the existing midas-dev pipeline keys.
    bucket  = "midas-dev-us-east-1-terraform-811391286931"
    region  = "us-east-1"
    key     = "aigtw/${path_relative_to_include()}/terraform.tfstate"
    encrypt = true

    # TODO(isolation): drop disable_bucket_update once we own the bucket (M-11). For now we
    # MUST NOT modify the SHARED midas-dev bucket's policies/ACLs from the AI Gateway pipeline.
    # In Terragrunt v0.48 this lives inside `config = {...}`, not at the remote_state level.
    disable_bucket_update            = true
    skip_bucket_versioning           = true
    skip_bucket_ssencryption         = true
    skip_bucket_root_access          = true
    skip_bucket_enforced_tls         = true
    skip_bucket_public_access_blocking = true
    skip_bucket_accesslogging        = true
    # DynamoDB locking intentionally omitted: matches the existing midas-dev Jenkinsfile_Deploy_App
    # pattern. Re-enable once midas-aigtw-dev-us-east-1-tflock is provisioned (M-11).
  }
}

inputs = {
  # === Tag metadata (MIDAS-owned, override upstream defaults) ===
  # Upstream defaults were BU="EXLerate.ai", owner="Turing", costcode="G081010".
  BU       = "MIDAS"
  owner    = "MIDAS"
  # costcode kept at upstream default "G081010" by user instruction; override here when MIDAS
  # cost code is assigned. Set explicitly so the source-of-truth is local, not upstream.
  costcode = "G081010"
  region   = "us-east-1"

  # === Identity / VPC (VPC + subnets are SHARED per Step 19; everything else DEDICATED) ===
  environment      = "dev"
  vpc_id           = "vpc-0c4d673f3e95a93eb"   # SHARED
  vpc_cidrs        = "10.72.134.0/23"

  # SHARED subnets per SOP §17.1
  subnet_ids = [
    "subnet-04d9f5b09b2dc9425", # us-east-1c, /25, 104 free IPs (also midas-eks-dev)
    "subnet-05c4fce53e16da9bc", # us-east-1a, /25, 102 free IPs (also midas-eks-dev)
    "subnet-0bc74e29f773eb7a4", # us-east-1a, /26, 58 free IPs
    "subnet-04f6c506a5098aa40", # us-east-1c, /26, 50 free IPs
    "subnet-0636beaf9f48cc482", # us-east-1a, /28 (RDS / Redis)
    "subnet-031582c139ff6d856", # us-east-1c, /28 (RDS / Redis)
  ]
  alb_subnets = [
    "subnet-0bc74e29f773eb7a4", # us-east-1a, /26
    "subnet-04f6c506a5098aa40", # us-east-1c, /26
  ]

  # === EKS — DEDICATED per Step 19 (Q14.1 = Option B) ===
  eks_cluster_name = "midas-eks-aigtw-dev"
  log_group_name   = "midas-aigtw-dev"
  # EKS-optimized AL2023 x86_64 AMI for cluster version 1.35 in us-east-1.
  # Discovered via: aws ssm get-parameter --name /aws/service/eks/optimized-ami/1.35/amazon-linux-2023/x86_64/standard/recommended/image_id
  # Release version: 1.35.3-20260415. Refresh with the same SSM lookup before each pipeline cut.
  ami_id           = "ami-0f8f4b97abe105a0f"
  instance_type    = ["t3.large", "t3.xlarge", "t3.2xlarge"]
  clickhouse_instance_type = ["m6i.xlarge"]

  scaling_config = {
    desired_size = 3
    max_size     = 6
    min_size     = 2
  }
  ch_scaling_config = {
    desired_size = 2
    max_size     = 4
    min_size     = 2
  }

  # === Cognito — DEDICATED (Q14.6) ===
  cognito_upn      = "midas-aigtw-dev-user-pool"
  cognito_domain   = "midas-aigtw-dev"

  # === SAML IdP (M-13) — corporate Entra/Azure AD federation ===
  # Langfuse SSO uses the DecisionAI team's ins-midas-dev-user-pool (us-east-1_5JL0dpXwK)
  # via a dedicated app client "langfuse-aigw-dev" created 2026-05-08.
  # The midas-aigtw-dev-user-pool does NOT own the SAML IdP — that lives on ins-midas pool.
  # enable_saml_identity_provider remains false: the Terraform-managed pool (midas-aigtw-dev)
  # does not need its own IdP. Auth is delegated to ins-midas-dev-user-pool at the Helm level
  # via AUTH_CUSTOM_ISSUER pointing to us-east-1_5JL0dpXwK.
  enable_saml_identity_provider = false
  cognito_saml_metadata_path    = ""
  cognito_saml_metadata_url     = "https://login.microsoftonline.com/<TENANT_ID>/federationmetadata/2007-06/federationmetadata.xml"

  # === ALB ingress controller IRSA — DEDICATED ===
  alb_irsa_account_name = "midas-aigtw-dev-alb-ingress-controller"

  # === ALB CIDR allowlists — match SOP §17.7 corporate Black Spider allowlist ===
  litellm_alb_cidr_blocks  = ["10.54.74.117/32", "10.54.67.114/32", "10.90.12.0/22", "10.72.134.0/23", "10.54.5.10/32"]
  langfuse_alb_cidr_blocks = ["10.54.74.117/32", "10.54.67.114/32", "10.90.12.0/22", "10.72.134.0/23", "10.54.5.10/32"]
  c1_api_alb_cidr_blocks   = ["10.54.74.117/32", "10.54.67.114/32", "10.90.12.0/22", "10.72.134.0/23", "10.54.5.10/32"]
  litellm_db_cidr_blocks   = ["10.72.134.0/23"]

  # === RDS — DEDICATED ===
  instance_class           = "db.t3.medium"
  db_engine_version        = "15"
  rds_alloc_storage        = 50
  max_alloc_storage        = 200
  skip_final_snapshot_flag = true   # DEV ONLY — flip for UAT/PROD
  deletion_protection      = false  # DEV ONLY — flip for UAT/PROD

  litellm_rds_db_name  = "midas_aigtw_dev_litellm"
  lite_db_username     = "llmproxy"
  langfuse_rds_db_name = "midas_aigtw_dev_langfuse"
  lang_db_username     = "langfuse_admin"
  c1_api_rds_db_name   = "midas_aigtw_dev_c1_api"
  c1_api_db_username   = "c1_api_admin"

  # === Secrets — DEDICATED ===
  # Empty strings on first apply: the upstream module's variables.tf defaults these to "".
  # TF will create the actual Secrets Manager secrets and emit IDs as outputs; on the second
  # apply we re-pin the literal IDs here (mirroring the upstream dev pattern at
  # ai_gateway/infra/terraform/environment/dev/terragrunt.hcl lines 85-87).
  litellm_stack_db_secret    = ""
  litellm_mastersalt_secret  = ""
  litellm_salt_secret        = ""

  # === IAM ===
  # Cluster service role — exists in MIDAS account (verified via `aws iam get-role`).
  service_role_arn   = "arn:aws:iam::811391286931:role/aws-service-role/eks.amazonaws.com/AWSServiceRoleForAmazonEKS"
  # SSO roles for cluster-admin access — IDs verified live via `aws iam list-roles` (§17.6).
  architect_role_arn = "arn:aws:iam::811391286931:role/aws-reserved/sso.amazonaws.com/AWSReservedSSO_uc-dev2.0-app.architects-ps_ed88ec1990bfba3d"
  developer_role_arn = "arn:aws:iam::811391286931:role/aws-reserved/sso.amazonaws.com/AWSReservedSSO_uc-dev2.0-sr.developer-ps_98b47d8fcc6511b7"
  admin_ro_arn       = "arn:aws:iam::811391286931:role/aws-reserved/sso.amazonaws.com/AWSReservedSSO_AWS_Admin_ReadOnly_52967e3c3ff93fab"

  # === LiteLLM ===
  # JFrog ELIMINATED (Step 15 + Q15.1): point at MIDAS ECR
  custom_litellm_URI  = "811391286931.dkr.ecr.us-east-1.amazonaws.com/midas-aigtw-dev-litellm"
  irsa_account_name   = "midas-aigtw-dev-litellm-irsa"
  sec_provider_class  = "midas-aigtw-dev-litellm-aws-secrets"

  # === ClickHouse ===
  ch_cluster_name = "midas-aigtw-dev-clickhouse"
  ch_ns           = "clickhouse"
  ch_host         = "clickhouse-clickhouse.clickhouse"
  # NOTE: upstream variables.tf does not declare ch_user — clickhouse helm chart values
  # carry the username instead (see deploy/ai_gateway/helm/clickhouse/values-midas-dev.yaml).

  # Legacy unused override (per-service ACM certs are managed in modules-midas/acm.tf).
  midas_acm_certificate_arn = ""

  # JFrog elimination (Q15.2 = submodule_toggle, now realised as in-tree fork).
  #
  # bootstrap_phase (see modules-midas/alb.tf + variables.tf):
  #   2 — NLB resources, listeners TCP:443, NLB→ALB target groups (type ALB), data.aws_lb
  #       lookups for litellm + langfuse stacks.
  #   3 — aws_lb_target_group_attachment: register each internal ALB on port 443 as the
  #       sole target of its NLB TG. Requires the ALB to already expose an HTTPS :443
  #       listener (created when ORD4 Langfuse / ORD5 LiteLLM Ingress applied). Run ORD1
  #       at phase 2, deploy ORD4+ORD5 at least once, then set phase 3 and re-run ORD1.
  #
  # Langfuse NLB path: midas-eks-aigtw-dev-nlb-langfuse :443 → TG midas-eks-aigtw-dev-lf-tg443
  # → ALB midas-aigtw-langfuse-alb-dev :443 (ACM = aws_acm_certificate.langfuse_cert).
  bootstrap_phase = 3

  use_jfrog_image_pull_secret = false
  aws_load_balancer_controller_image_repo = "811391286931.dkr.ecr.us-east-1.amazonaws.com/midas-aigtw-dev-aws-load-balancer-controller"
  # MIDAS: v3.1.0 was the CHART version, not the controller image tag (the controller's
  # latest is v2.x.y). The dest ECR repo was mirrored from the existing
  # midas-dev-aws-load-balancer-controller:v2.8.1 (skopeo, see SOP Step 31). If you bump
  # the chart, also bump this tag to a real `eks/aws-load-balancer-controller` image tag
  # listed at gallery.ecr.aws/eks/aws-load-balancer-controller and re-mirror.
  aws_load_balancer_controller_image_tag  = "v2.8.1"
}

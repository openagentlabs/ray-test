variable "BU" {
  type    = string
  default = "EXLerate.ai"
}

variable "costcode" {
  type    = string
  default = "G081010"
}

variable "region" {
  type    = string
  default = "us-east-1"
}

variable "owner" {
  type    = string
  default = "Turing"
}

variable "eks_cluster_name" {
  type = string
}

variable "environment" {
  type = string
}

variable "litellm_stack_db_secret" {
  type    = string
  default = ""
}

variable "litellm_mastersalt_secret" {
  type    = string
  default = ""
}

variable "litellm_salt_secret" {
  type    = string
  default = ""
}

variable "vpc_id" {
  type = string
}

variable "vpc_cidrs" {
  type = string
}

variable "subnet_ids" {
  type = list(string)
}

variable "eks_subnet_ids" {
  type    = list(string)
  default = [""]
}

variable "eks_cluster_version" {
  type    = string
  default = "1.35"
}

variable "ami_id" {
  type = string
}

variable "ami_type" {
  type    = string
  default = "AL2023_x86_64_STANDARD"
}

variable "instance_type" {
  type = list(string)
}

variable "log_group_name" {
  type = string
}

variable "eks_log_types" {
  type    = list(string)
  default = ["api", "authenticator", "scheduler", "controllerManager", "audit"]
}

variable "eks_addons" {
  type = map(string)
  default = {
    "vpc-cni"                               = "v1.21.1-eksbuild.3",
    "kube-proxy"                            = "v1.35.0-eksbuild.2",
    "coredns"                               = "v1.13.2-eksbuild.3",
    "eks-pod-identity-agent"                = "v1.3.10-eksbuild.2",
    "aws-secrets-store-csi-driver-provider" = "v2.1.1-eksbuild.1" # ASCP
    "aws-ebs-csi-driver"                    = "v1.54.0-eksbuild.1"
  }
}

variable "service_role_arn" {
  type = string
}

variable "architect_role_arn" {
  type = string
}

variable "scaling_config" {
  type = object({
    desired_size = number
    max_size     = number
    min_size     = number
  })
}

variable "instance_class" {
  type    = string
  default = "db.t3.micro"
}

variable "db_engine_version" {
  type = string
}

variable "rds_alloc_storage" {
  type = string
}

variable "rds_subnet_ids" {
  type    = list(string)
  default = [""]
}

variable "max_alloc_storage" {
  type = string
}

variable "litellm_rds_db_name" {
  type = string
}

variable "langfuse_rds_db_name" {
  type = string
}

variable "c1_api_rds_db_name" {
  type = string
}

variable "c1_api_db_username" {
  type = string
}

variable "lang_db_username" {
  type = string
}

variable "lite_db_username" {
  type = string
}

variable "skip_final_snapshot_flag" {
  type    = bool
  default = false
}

variable "deletion_protection" {
  type    = bool
  default = true
}

variable "developer_role_arn" {
  type = string
}

variable "admin_ro_arn" {
  type = string
}

variable "litellm_hc" {
  type    = string
  default = "litellm"
}

variable "litellm_ns" {
  type    = string
  default = "litellm"
}

variable "langfuse_ns" {
  type    = string
  default = "langfuse"
}

variable "custom_litellm_URI" {
  type = string
}

variable "sec_provider_class" {
  type    = string
  default = "litellm-aws-secrets"
}

variable "irsa_account_name" {
  type = string
}

variable "clickhouse_instance_type" {
  type = list(string)
}

variable "ch_scaling_config" {
  type = object({
    desired_size = number
    max_size     = number
    min_size     = number
  })
}

variable "ch_cluster_name" {
  type = string
}

variable "ch_ns" {
  type = string
}

variable "ch_host" {
  type = string
}

variable "ch_volume_size" {
  type    = number
  default = 20
}

variable "ch_keeper_replica" {
  type    = number
  default = 3
}

variable "redis_cache_nodes" {
  type    = number
  default = 2
}

variable "redis_node_type" {
  type    = string
  default = "cache.t3.micro"
}

variable "alb_irsa_account_name" {
  type = string
}

variable "aws_load_balancer_controller_chart_version" {
  type    = string
  default = "3.1.0"
}

variable "aws_public_ecr_registry_url" {
  type    = string
  default = "public.ecr.arws"
}

variable "alb_subnets" {
  type = list(string)
}

variable "cognito_upn" {
  type = string
}

variable "cognito_domain" {
  type = string
}

# SAML IdP metadata for EXLerateAI — Cognito requires provider_details (MetadataFile and/or MetadataURL).
# Set at least one of path or URL (same as console "Upload metadata document" vs fetching federation metadata).
variable "cognito_saml_metadata_path" {
  type        = string
  description = "Optional path to SAML metadata XML; passed as Cognito provider_details MetadataFile."
  default     = ""
}

variable "cognito_saml_metadata_url" {
  type        = string
  description = "Optional federation metadata URL (e.g. Entra https://login.microsoftonline.com/<tenant-id>/federationmetadata/2007-06/federationmetadata.xml); passed as MetadataURL."
  default     = ""
}

variable "jfrog_regcred_arn" {
  type    = string
  default = ""
}

variable "c1_api_ns" {
  type    = string
  default = "c1-api"
}

variable "litellm_alb_cidr_blocks" {
  type = list(string)
}

variable "litellm_db_cidr_blocks" {
  type = list(string)
}

variable "langfuse_alb_cidr_blocks" {
  type = list(string)
}

variable "c1_api_alb_cidr_blocks" {
  type = list(string)
}

variable "c1_api_sec_provider_class" {
  type    = string
  default = "c1-api-aws-secrets"
}

# === MIDAS in-tree fork variables ===

# Optional override ARN for all AI Gateway ALB ingress ConfigMaps (LiteLLM,
# Langfuse, C1). When empty, the ARN of `aws_acm_certificate.exlerate-c1-api-cert`
# is used so every app shares one certificate (same ARN may attach to multiple ALBs).
variable "midas_acm_certificate_arn" {
  type    = string
  default = ""
}

# Fully-qualified MIDAS ECR image refs used by upstream modules that previously
# pulled from JFrog. ORD2 image-bootstrap will mirror these from upstream/public
# registries to MIDAS ECR.
variable "aws_load_balancer_controller_image_repo" {
  type        = string
  description = "MIDAS ECR repository for aws-load-balancer-controller (replaces upstream JFrog reference)."
  default     = "811391286931.dkr.ecr.us-east-1.amazonaws.com/midas-aigtw-dev-aws-load-balancer-controller"
}

variable "aws_load_balancer_controller_image_tag" {
  type    = string
  default = "v3.1.0"
}

# When false (MIDAS default), the alb chart is rendered WITHOUT the jfrog-regcred
# imagePullSecret — pulling from MIDAS ECR uses IRSA instead.
variable "use_jfrog_image_pull_secret" {
  type    = bool
  default = false
}

# MIDAS in-tree fork: staged-deploy phase flag.
#   1 = first apply (creates VPC dependencies, RDS, Redis, EKS cluster, secrets,
#       ECR pulls, IRSA, helm releases that don't yet need a real ALB). Skips:
#         - data.aws_lb lookups (ALB doesn't exist yet)
#         - aws_lb_target_group / _attachment / _listener that ride on those ALBs
#         - kubernetes_manifest resources (kubernetes_manifest requires a live
#           cluster at PLAN time, which doesn't exist on first apply).
#   2 = NLB + listener + NLB→ALB target groups + data.aws_lb discovery (litellm/langfuse).
#   3 = aws_lb_target_group_attachment for each NLB TG → ALB:443 (requires Ingress to have
#       created HTTPS listeners first — run ORD4/ORD5 then bump phase and ORD1 apply).
# Flip values in deploy/ai_gateway/terraform/environment/dev/terragrunt.hcl `inputs`.
variable "bootstrap_phase" {
  type    = number
  default = 1
}

# MIDAS in-tree fork: gate the corporate-SAML IdP creation. The upstream module
# always tries to create a Cognito SAML IdP "EXLerateAI" using SAML metadata
# fetched from the cognito-sso-credentials secret. On a fresh MIDAS deploy that
# secret holds the placeholder "PopulateMe", which is not valid SAML XML, so
# the IdP creation fails and downstream user-pool-client creates fail too
# (they reference the non-existent IdP via `supported_identity_providers`).
# Default false: skip IdP + drop "EXLerateAI" from supported_identity_providers.
# Flip to true once the corporate Entra/Azure AD federation metadata XML has
# been put into the cognito-sso-credentials secret (see deploy/ai_gateway/scripts/
# populate-secrets.sh and SOP item M-13).
variable "enable_saml_identity_provider" {
  type    = bool
  default = false
}
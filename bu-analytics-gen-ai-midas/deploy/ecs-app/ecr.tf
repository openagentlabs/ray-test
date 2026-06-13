# -----------------------------------------------------------------------------
# Amazon ECR - container image registries for MIDAS (module: ./modules/ecr).
# Legacy repo midas-{env}-app plus three application service repositories.
# EKS nodes pull via AmazonEC2ContainerRegistryReadOnly on the node IAM role.
# -----------------------------------------------------------------------------

module "ecr" {
  source = "./modules/ecr"

  aws_account_id = var.aws_account_id
  environment    = var.environment
  aws_region     = var.aws_region
}

module "ecr_midas_web_frontend_svc" {
  source = "./modules/ecr"

  aws_account_id         = var.aws_account_id
  environment            = var.environment
  aws_region             = var.aws_region
  repository_name_suffix = "midas-web-frontend-svc"
}

module "ecr_midas_api_backend_svc" {
  source = "./modules/ecr"

  aws_account_id         = var.aws_account_id
  environment            = var.environment
  aws_region             = var.aws_region
  repository_name_suffix = "midas-api-backend-svc"
}

module "ecr_midas_graph_svc" {
  source = "./modules/ecr"

  aws_account_id         = var.aws_account_id
  environment            = var.environment
  aws_region             = var.aws_region
  repository_name_suffix = "midas-graph-svc"
}

# ECR repository for the ec2-mt-test one-shot batch Job image.
# Shares the same module pattern as the application service repos above.
module "ecr_midas_ec2_mt_test_svc" {
  source = "./modules/ecr"

  aws_account_id         = var.aws_account_id
  environment            = var.environment
  aws_region             = var.aws_region
  repository_name_suffix = "midas-ec2-mt-test-svc"
}

output "ecr_repository_name" {
  description = "ECR repository name for legacy midas-{env}-app container images."
  value       = module.ecr.repository_name
}

output "ecr_repository_arn" {
  description = "ECR repository ARN (legacy midas-{env}-app)."
  value       = module.ecr.repository_arn
}

output "ecr_repository_url" {
  description = "ECR repository URL without tag (legacy midas-{env}-app)."
  value       = module.ecr.repository_url
}

output "ecr_midas_web_frontend_svc_repository_url" {
  description = "ECR repository URL for midas-web-frontend-svc (no tag)."
  value       = module.ecr_midas_web_frontend_svc.repository_url
}

output "ecr_midas_api_backend_svc_repository_url" {
  description = "ECR repository URL for midas-api-backend-svc (no tag)."
  value       = module.ecr_midas_api_backend_svc.repository_url
}

output "ecr_midas_graph_svc_repository_url" {
  description = "ECR repository URL for midas-graph-svc (no tag)."
  value       = module.ecr_midas_graph_svc.repository_url
}

output "ecr_midas_ec2_mt_test_svc_repository_url" {
  description = "ECR repository URL for midas-ec2-mt-test-svc (no tag)."
  value       = module.ecr_midas_ec2_mt_test_svc.repository_url
}

output "ecr_router_svc_repository_url" {
  description = "ECR repository URL for router-svc (no tag)."
  value       = module.ecr-router-svc.repository_url
}

output "ecr_envoy_router_repository_url" {
  description = "ECR repository URL for envoy-router (no tag)."
  value       = module.ecr-envoy-router.repository_url
}

# -----------------------------------------------------------------------------

variable "protected_tags" {
  description = "Name of image tag prefixes that should not be destroyed."
  type        = list(string)
  default     = []
}

variable "allow_delete" {
  description = "Should the resources be allowed to be deleted? This triggers `enable_deletion_protection` or `force_destroy` in certain modules."
  type        = bool
  default     = true
}

locals {
  project = "midas"
  protected_tag_rules = [
    for index, tagPrefix in zipmap(range(length(var.protected_tags)), tolist(var.protected_tags)) :
    {
      rulePriority = tonumber(index) + 1
      description  = "Protects images tagged with ${tagPrefix}"
      selection = {
        tagStatus     = "tagged"
        tagPrefixList = [tagPrefix]
        countType     = "imageCountMoreThan"
        countNumber   = 999999
      }
      action = {
        type = "expire"
      }
    }
  ]

  untagged_image_rule = [
    {
      rulePriority = length(var.protected_tags) + 1
      description  = "Remove untagged images"
      selection = {
        tagStatus   = "untagged"
        countType   = "sinceImagePushed"
        countUnit   = "days"
        countNumber = 1
      }
      action = {
        type = "expire"
      }
    }
  ]

  remove_old_image_rule = [
    {
      rulePriority = length(var.protected_tags) + 2
      description  = "Keep last 30 images",
      selection = {
        tagStatus   = "any"
        countType   = "imageCountMoreThan"
        countNumber = 30
      }
      action = {
        type = "expire"
      }
    }
  ]
}

module "ecr-kms" {
  #checkov:skip=CKV_TF_1:
  source  = "terraform-aws-modules/kms/aws"
  version = "4.2.0"

  description             = "Key for ECR"
  key_usage               = "ENCRYPT_DECRYPT"
  deletion_window_in_days = var.deletion_window_in_days

  # Policy
  enable_default_policy = true
  key_administrators    = ["arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"]
  key_owners            = ["arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/midas-deployer-role"]

  # Aliases
  aliases                 = ["exl/ecr"]
  aliases_use_name_prefix = true
}

module "ecr-web-frontend-svc" {
  #checkov:skip=CKV_TF_1:
  source  = "terraform-aws-modules/ecr/aws"
  version = "3.2.0"

  repository_name = "${local.project}/web-frontend-svc"

  repository_image_tag_mutability = "IMMUTABLE_WITH_EXCLUSION"
  repository_image_tag_mutability_exclusion_filter = [
    {
      filter      = "latest"
      filter_type = "WILDCARD"
    }
  ]
  repository_read_access_arns = [
    "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root",
  ]
  repository_read_write_access_arns = [
    "arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/midas-deployer-role",
  ]
  repository_lifecycle_policy = jsonencode({
    rules = concat(
      local.protected_tag_rules,
      #local.untagged_image_rule,
      local.remove_old_image_rule,
    )
  })
  repository_encryption_type    = "KMS"
  repository_kms_key            = module.ecr-kms.key_arn
  repository_image_scan_on_push = false
  repository_force_delete       = var.allow_delete
}

module "ecr-api-backend-svc" {
  #checkov:skip=CKV_TF_1:
  source  = "terraform-aws-modules/ecr/aws"
  version = "3.2.0"

  repository_name = "${local.project}/api-backend-svc"

  repository_image_tag_mutability = "IMMUTABLE_WITH_EXCLUSION"
  repository_image_tag_mutability_exclusion_filter = [
    {
      filter      = "latest"
      filter_type = "WILDCARD"
    }
  ]
  repository_read_access_arns = [
    "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root",
  ]
  repository_read_write_access_arns = [
    "arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/midas-deployer-role",
  ]
  repository_lifecycle_policy = jsonencode({
    rules = concat(
      local.protected_tag_rules,
      #local.untagged_image_rule,
      local.remove_old_image_rule,
    )
  })
  repository_encryption_type    = "KMS"
  repository_kms_key            = module.ecr-kms.key_arn
  repository_image_scan_on_push = false
  repository_force_delete       = var.allow_delete
}

module "ecr-graph-svc" {
  #checkov:skip=CKV_TF_1:
  source  = "terraform-aws-modules/ecr/aws"
  version = "3.2.0"

  repository_name = "${local.project}/graph-svc"

  repository_image_tag_mutability = "IMMUTABLE_WITH_EXCLUSION"
  repository_image_tag_mutability_exclusion_filter = [
    {
      filter      = "latest"
      filter_type = "WILDCARD"
    }
  ]
  repository_read_access_arns = [
    "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root",
  ]
  repository_read_write_access_arns = [
    "arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/midas-deployer-role",
  ]
  repository_lifecycle_policy = jsonencode({
    rules = concat(
      local.protected_tag_rules,
      #local.untagged_image_rule,
      local.remove_old_image_rule,
    )
  })
  repository_encryption_type    = "KMS"
  repository_kms_key            = module.ecr-kms.key_arn
  repository_image_scan_on_push = false
  repository_force_delete       = var.allow_delete
}

module "ecr-ec2-mt-test-svc" {
  #checkov:skip=CKV_TF_1:
  source  = "terraform-aws-modules/ecr/aws"
  version = "3.2.0"

  repository_name = "${local.project}/ec2-mt-test-svc"

  repository_image_tag_mutability = "IMMUTABLE_WITH_EXCLUSION"
  repository_image_tag_mutability_exclusion_filter = [
    {
      filter      = "latest"
      filter_type = "WILDCARD"
    }
  ]
  repository_read_access_arns = [
    "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root",
  ]
  repository_read_write_access_arns = [
    "arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/midas-deployer-role",
  ]
  repository_lifecycle_policy = jsonencode({
    rules = concat(
      local.protected_tag_rules,
      #local.untagged_image_rule,
      local.remove_old_image_rule,
    )
  })
  repository_encryption_type    = "KMS"
  repository_kms_key            = module.ecr-kms.key_arn
  repository_image_scan_on_push = false
  repository_force_delete       = var.allow_delete
}

module "ecr-envoy-router" {
  #checkov:skip=CKV_TF_1:
  source  = "terraform-aws-modules/ecr/aws"
  version = "3.2.0"

  repository_name = "${local.project}/envoy-router"

  repository_image_tag_mutability = "IMMUTABLE_WITH_EXCLUSION"
  repository_image_tag_mutability_exclusion_filter = [
    {
      filter      = "latest"
      filter_type = "WILDCARD"
    }
  ]
  repository_read_access_arns = [
    "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root",
  ]
  repository_read_write_access_arns = [
    "arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/midas-deployer-role",
  ]
  repository_lifecycle_policy = jsonencode({
    rules = concat(
      local.protected_tag_rules,
      #local.untagged_image_rule,
      local.remove_old_image_rule,
    )
  })
  repository_encryption_type    = "KMS"
  repository_kms_key            = module.ecr-kms.key_arn
  repository_image_scan_on_push = false
  repository_force_delete       = var.allow_delete
}

module "ecr-router-svc" {
  #checkov:skip=CKV_TF_1:
  source  = "terraform-aws-modules/ecr/aws"
  version = "3.2.0"

  repository_name = "${local.project}/router-svc"

  repository_image_tag_mutability = "IMMUTABLE_WITH_EXCLUSION"
  repository_image_tag_mutability_exclusion_filter = [
    {
      filter      = "latest"
      filter_type = "WILDCARD"
    }
  ]
  repository_read_access_arns = [
    "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root",
  ]
  repository_read_write_access_arns = [
    "arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/midas-deployer-role",
  ]
  repository_lifecycle_policy = jsonencode({
    rules = concat(
      local.protected_tag_rules,
      #local.untagged_image_rule,
      local.remove_old_image_rule,
    )
  })
  repository_encryption_type    = "KMS"
  repository_kms_key            = module.ecr-kms.key_arn
  repository_image_scan_on_push = false
  repository_force_delete       = var.allow_delete
}


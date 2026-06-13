# router.svc DynamoDB tables — schemas must match repository models under
# router.svc/server/src/solutions_service/database/

variable "service_name" {
  description = "Must match router.svc [app].service_name for DynamoDB table prefixing."
  type        = string
  default     = "router-svc"
}

variable "table_suffixes" {
  description = "Logical DynamoDB table suffixes (physical: {service_name}-{suffix})."
  type = object({
    backend_pool       = string
    login_pod_pool     = string
    user_assignments   = string
    assignment_events  = string
    solution_documents = string
    service_config     = string
  })
  default = {
    backend_pool       = "backend-pool"
    login_pod_pool     = "login-pod-pool"
    user_assignments   = "user-assignments"
    assignment_events  = "assignment-events"
    solution_documents = "solution-documents"
    service_config     = "service-config"
  }
}

variable "deletion_window_in_days" {
  description = "The waiting period, specified in number of days. After the waiting period ends, AWS KMS deletes the KMS key. If you specify a value, it must be between 7 and 30, inclusive."
  type        = number
  default     = 7
}

data "aws_caller_identity" "current" {}

locals {
  service_prefix = replace(lower(trimspace(var.service_name)), "_", "-")

  physical_names = {
    backend_pool       = "${local.service_prefix}-${var.table_suffixes.backend_pool}"
    login_pod_pool     = "${local.service_prefix}-${var.table_suffixes.login_pod_pool}"
    user_assignments   = "${local.service_prefix}-${var.table_suffixes.user_assignments}"
    assignment_events  = "${local.service_prefix}-${var.table_suffixes.assignment_events}"
    solution_documents = "${local.service_prefix}-${var.table_suffixes.solution_documents}"
    service_config     = "${local.service_prefix}-${var.table_suffixes.service_config}"
  }
}

# -----------------------------------------------------------------------------

#module "dynamodb-kms" {
#  #checkov:skip=CKV_TF_1:
#  source  = "terraform-aws-modules/kms/aws"
#  version = "4.2.0"
#
#  description             = "Key for DynamoDB"
#  key_usage               = "ENCRYPT_DECRYPT"
#  deletion_window_in_days = var.deletion_window_in_days
#
#  # Policy
#  enable_default_policy = true
#  key_administrators    = ["arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"]
#  key_owners            = ["arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/midas-deployer-role"]
#
#  # Aliases
#  aliases                 = ["exl/dynamodb"]
#  aliases_use_name_prefix = true
#}
#
## backend_pool — PK pod_id; GSI backend-pool-by-state (state → pod_id)
#module "dynamodb-backend_pool" {
#  #checkov:skip=CKV_TF_1:
#  source  = "terraform-aws-modules/dynamodb-table/aws"
#  version = "v5.5.0"
#
#  name     = local.physical_names.backend_pool
#  hash_key = "pod_id"
#
#  attributes = [
#    {
#      name = "pod_id"
#      type = "S"
#    },
#    {
#      name = "state"
#      type = "S"
#    }
#  ]
#
#  global_secondary_indexes = [{
#    name            = "backend-pool-by-state"
#    hash_key        = "state"
#    range_key       = "pod_id"
#    projection_type = "ALL"
#  }]
#
#  point_in_time_recovery_enabled     = true
#  server_side_encryption_enabled     = true
#  server_side_encryption_kms_key_arn = module.dynamodb-kms.key_arn
#
#  tags = {
#    Table = "backend_pool"
#  }
#}
#
## login_pod_pool — PK pod_id; GSI login-pod-pool-by-state (state → pod_id)
#module "dynamodb-login_pod_pool" {
#  #checkov:skip=CKV_TF_1:
#  source  = "terraform-aws-modules/dynamodb-table/aws"
#  version = "v5.5.0"
#
#  name     = local.physical_names.login_pod_pool
#  hash_key = "pod_id"
#
#  attributes = [
#    {
#      name = "pod_id"
#      type = "S"
#    },
#    {
#      name = "state"
#      type = "S"
#    }
#  ]
#
#  global_secondary_indexes = [{
#    name            = "login-pod-pool-by-state"
#    hash_key        = "state"
#    range_key       = "pod_id"
#    projection_type = "ALL"
#  }]
#
#  point_in_time_recovery_enabled     = true
#  server_side_encryption_enabled     = true
#  server_side_encryption_kms_key_arn = module.dynamodb-kms.key_arn
#
#  tags = {
#    Table = "login_pod_pool"
#  }
#}
#
## user_assignments — PK sub; GSI assignments-by-pod (pod_id → sub)
#module "dynamodb-user_assignments" {
#  #checkov:skip=CKV_TF_1:
#  source  = "terraform-aws-modules/dynamodb-table/aws"
#  version = "v5.5.0"
#
#  name     = local.physical_names.user_assignments
#  hash_key = "sub"
#
#  attributes = [
#    {
#      name = "sub"
#      type = "S"
#    },
#    {
#      name = "pod_id"
#      type = "S"
#    }
#  ]
#
#  global_secondary_indexes = [{
#    name            = "assignments-by-pod"
#    hash_key        = "pod_id"
#    range_key       = "sub"
#    projection_type = "ALL"
#  }]
#
#  point_in_time_recovery_enabled     = true
#  server_side_encryption_enabled     = true
#  server_side_encryption_kms_key_arn = module.dynamodb-kms.key_arn
#
#  tags = {
#    Table = "user_assignments"
#  }
#}
#
## assignment_events — PK event_id (audit trail)
#module "dynamodb-assignment_events" {
#  #checkov:skip=CKV_TF_1:
#  source  = "terraform-aws-modules/dynamodb-table/aws"
#  version = "v5.5.0"
#
#  name     = local.physical_names.assignment_events
#  hash_key = "event_id"
#
#  attributes = [
#    {
#      name = "event_id"
#      type = "S"
#    }
#  ]
#
#  point_in_time_recovery_enabled     = true
#  server_side_encryption_enabled     = true
#  server_side_encryption_kms_key_arn = module.dynamodb-kms.key_arn
#
#  tags = {
#    Table = "assignment_events"
#  }
#}
#
## solution_documents — PK id; GSI solution-documents (solution_id → id)
#module "dynamodb-solution_documents" {
#  #checkov:skip=CKV_TF_1:
#  source  = "terraform-aws-modules/dynamodb-table/aws"
#  version = "v5.5.0"
#
#  name     = local.physical_names.solution_documents
#  hash_key = "id"
#
#  attributes = [
#    {
#      name = "id"
#      type = "S"
#    },
#    {
#      name = "solution_id"
#      type = "S"
#    }
#  ]
#
#  global_secondary_indexes = [{
#    name            = "solution-documents"
#    hash_key        = "solution_id"
#    range_key       = "id"
#    projection_type = "ALL"
#  }]
#
#  point_in_time_recovery_enabled     = true
#  server_side_encryption_enabled     = true
#  server_side_encryption_kms_key_arn = module.dynamodb-kms.key_arn
#
#  tags = {
#    Table = "solution_documents"
#  }
#}
#
## service_config — PK config_key (non-environment tunables)
#module "dynamodb-service_config" {
#  #checkov:skip=CKV_TF_1:
#  source  = "terraform-aws-modules/dynamodb-table/aws"
#  version = "v5.5.0"
#
#  name     = local.physical_names.service_config
#  hash_key = "config_key"
#
#  attributes = [
#    {
#      name = "config_key"
#      type = "S"
#    }
#  ]
#
#  point_in_time_recovery_enabled     = true
#  server_side_encryption_enabled     = true
#  server_side_encryption_kms_key_arn = module.dynamodb-kms.key_arn
#
#  tags = {
#    Table = "service_config"
#  }
#}

# -----------------------------------------------------------------------------

variable "kubernetes_namespace" {
  type        = string
  default     = "routing"
  description = "Namespace for the routing-tier Helm release."
}

variable "kubernetes_service_account" {
  type        = string
  default     = "pod-manager"
  description = "Service account name for router.svc IRSA."
}

module "iam_pod_manager" {
  source = "./modules/iam-pod-manager"

  role_name            = "${var.environment}-pod-manager-irsa"
  oidc_provider_arn    = module.eks_alb_controller_iam.oidc_provider_arn
  namespace            = var.kubernetes_namespace
  service_account_name = var.kubernetes_service_account
  dynamodb_table_arns = [
#    module.dynamodb-backend_pool.dynamodb_table_arn,
#    module.dynamodb-login_pod_pool.dynamodb_table_arn,
#    module.dynamodb-user_assignments.dynamodb_table_arn,
#    module.dynamodb-assignment_events.dynamodb_table_arn,
#    module.dynamodb-solution_documents.dynamodb_table_arn,
#    module.dynamodb-service_config.dynamodb_table_arn,
    "arn:aws:dynamodb:us-east-1:${data.aws_caller_identity.current.account_id}:table/*",
  ]
}

#module "eks_alb_controller" {
#  source = "./modules/eks-alb-controller"
#
#  cluster_name      = module.eks.eks_cluster_name
#  oidc_provider_arn = module.eks_alb_controller_iam.oidc_provider_arn
#  oidc_provider_url = module.eks.oidc_issuer_url
#  vpc_id            = var.eks_vpc_id
#  aws_region        = var.aws_region
#
#  depends_on = [module.eks]
#}

output "pod_manager_irsa_role_arn" {
  description = "Set routing-tier.serviceAccount.roleArn in Helm values."
  value       = module.iam_pod_manager.role_arn
}

output "service_name" {
  description = "Service name prefix (must match Helm / app_config)."
  value       = var.service_name
}


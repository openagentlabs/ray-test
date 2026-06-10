module "vpc" {
  source = "../vpc_fargate"

  solution              = var.solution
  vpc_cidr              = var.vpc_cidr
  cluster_name          = var.cluster_name
  existing_vpc_id       = var.existing_vpc_id
  existing_subnet_ids   = var.existing_subnet_ids
}

module "eks_platform" {
  source = "../eks_platform"

  solution              = var.solution
  cluster_name          = var.cluster_name
  namespace             = var.namespace
  vpc_id                = module.vpc.vpc_id
  subnet_ids            = module.vpc.subnet_ids
  fargate_subnet_ids    = module.vpc.fargate_subnet_ids
  log_retention_in_days = var.cloudwatch_log_retention_in_days
}

module "eks_cloudwatch" {
  source = "../eks_cloudwatch"

  providers = {
    kubernetes = kubernetes.eks
  }

  solution                        = var.solution
  cluster_name                    = module.eks_platform.cluster_name
  subnet_ids                      = module.vpc.fargate_subnet_ids
  oidc_provider_arn               = module.eks_platform.oidc_provider_arn
  oidc_provider_url               = module.eks_platform.oidc_provider_url
  fargate_pod_execution_role_arn  = module.eks_platform.fargate_pod_execution_role_arn
  fargate_pod_execution_role_name = module.eks_platform.fargate_pod_execution_role_name
  application_log_group_arns      = var.application_log_group_arns
  application_log_group_names     = var.application_log_group_names
  retention_in_days               = var.cloudwatch_log_retention_in_days

  depends_on = [module.eks_platform]
}

data "aws_caller_identity" "current" {}

data "aws_availability_zones" "available" {
  state = "available"
}

locals {
  account_id         = data.aws_caller_identity.current.account_id
  deploy_target      = "aws"
  cluster_name       = coalesce(var.eks_cluster_name, "${var.environment}-pod-manager")
  availability_zones = slice(data.aws_availability_zones.available.names, 0, 2)
  iam_role_name      = coalesce(var.iam_role_name, "${var.environment}-pod-manager-irsa")
  vpc_id             = var.create_vpc ? module.vpc[0].vpc_id : var.existing_vpc_id
  private_subnet_ids = var.create_vpc ? module.vpc[0].private_subnet_ids : var.existing_private_subnet_ids
}

module "vpc" {
  count  = var.create_vpc ? 1 : 0
  source = "../../modules/vpc"

  name = "${var.environment}-pod-manager"
  cidr = var.vpc_cidr
  azs  = local.availability_zones

  private_subnet_cidrs = var.private_subnet_cidrs
  public_subnet_cidrs  = var.public_subnet_cidrs

  tags = {
    Environment = var.environment
  }
}

variable "node_subnet_ids" {
  type        = list(string)
  default     = []
  description = "Optional override subnet IDs for managed node groups; defaults to private_subnet_ids."
}

module "eks" {
  source = "../../modules/eks"

  cluster_name       = local.cluster_name
  cluster_version    = var.eks_cluster_version
  vpc_id             = local.vpc_id
  private_subnet_ids = local.private_subnet_ids
  node_subnet_ids    = local.private_subnet_ids

  node_instance_types = var.eks_node_instance_types
  node_desired_size   = var.eks_node_desired_size
  node_min_size       = var.eks_node_min_size
  node_max_size       = var.eks_node_max_size

  tags = {
    Environment = var.environment
  }
}

data "aws_eks_cluster_auth" "this" {
  name = module.eks.cluster_name
}

module "ecr" {
  source = "../../modules/ecr-repositories"

  repository_names = var.ecr_repository_names
  tags = {
    Environment = var.environment
  }
}

module "iam_pod_manager" {
  source = "../../modules/iam-pod-manager"

  role_name               = local.iam_role_name
  oidc_provider_arn       = module.eks.oidc_provider_arn
  namespace               = var.kubernetes_namespace
  service_account_name    = var.kubernetes_service_account
  database_url_secret_arn = var.database_url_secret_arn
  tags = {
    Environment = var.environment
  }
}

module "eks_alb_controller" {
  source = "../../modules/eks-alb-controller"

  cluster_name      = module.eks.cluster_name
  oidc_provider_arn = module.eks.oidc_provider_arn
  oidc_provider_url = module.eks.cluster_oidc_issuer_url
  vpc_id            = local.vpc_id
  aws_region        = var.aws_region

  tags = {
    Environment = var.environment
  }

  depends_on = [module.eks]
}

resource "aws_ec2_tag" "cluster_subnet" {
  for_each = toset(local.private_subnet_ids)

  resource_id = each.value
  key         = "kubernetes.io/cluster/${local.cluster_name}"
  value       = "shared"
}

resource "aws_ec2_tag" "elb_subnet" {
  for_each = toset(local.private_subnet_ids)

  resource_id = each.value
  key         = "kubernetes.io/role/elb"
  value       = "1"
}

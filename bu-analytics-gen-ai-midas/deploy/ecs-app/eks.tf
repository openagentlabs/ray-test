# -----------------------------------------------------------------------------
# EKS cluster + managed node group (module: ./modules/eks).
# Same registration pattern as deploy/ecs-app/s3.tf.
# -----------------------------------------------------------------------------

module "eks" {
  source = "./modules/eks"

  aws_account_id = var.aws_account_id
  environment    = var.environment
  aws_region     = var.aws_region

  vpc_id              = var.eks_vpc_id
  cluster_subnet_ids  = var.eks_cluster_subnet_ids
  cluster_name_prefix = var.eks_cluster_name_prefix
  node_subnet_ids     = var.eks_node_subnet_ids

  node_instance_types = var.eks_node_instance_types
  node_desired_size   = var.eks_node_desired_size
  node_min_size       = var.eks_node_min_size
  node_max_size       = var.eks_node_max_size

  cluster_api_https_ingress_cidrs = var.eks_cluster_api_https_ingress_cidrs
}

output "eks_cluster_name" {
  description = "EKS cluster name."
  value       = module.eks.eks_cluster_name
}

output "eks_cluster_endpoint" {
  description = "Kubernetes API endpoint (private when cluster has no public endpoint)."
  value       = module.eks.eks_cluster_endpoint
}

output "eks_cluster_arn" {
  description = "EKS cluster ARN."
  value       = module.eks.eks_cluster_arn
}

output "eks_node_group_name" {
  description = "Managed node group name."
  value       = module.eks.eks_node_group_name
}

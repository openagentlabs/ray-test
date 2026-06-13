# -----------------------------------------------------------------------------
# Ubuntu EC2 test instance with SSM Session Manager (module: ./modules/ec2-ssm-test).
# Optional clone: same module/settings, distinct AWS names; subnet pinned to primary for parity.
# -----------------------------------------------------------------------------

module "ec2_ssm_test" {
  source = "./modules/ec2-ssm-test"

  aws_account_id = var.aws_account_id
  environment    = var.environment
  vpc_id         = var.ec2_ssm_test_vpc_id
  subnet_id      = var.ec2_ssm_test_subnet_id
  aws_region     = var.aws_region

  enable_eks_kubectl_iam = true
  eks_cluster_name       = module.eks.eks_cluster_name
  eks_kubernetes_version = module.eks.eks_cluster_version
}

module "ec2_ssm_test_clone" {
  count  = var.ec2_ssm_test_clone_enabled ? 1 : 0
  source = "./modules/ec2-ssm-test"

  aws_account_id       = var.aws_account_id
  environment          = var.environment
  vpc_id               = var.ec2_ssm_test_vpc_id
  subnet_id            = module.ec2_ssm_test.subnet_id
  aws_region           = var.aws_region
  resource_name_suffix = "-clone"
  # Match EKS worker vCPU/RAM (single-type node group uses eks_node_instance_types[0]).
  instance_type          = var.eks_node_instance_types[0]
  enable_eks_kubectl_iam = true
  eks_cluster_name       = module.eks.eks_cluster_name
  eks_kubernetes_version = module.eks.eks_cluster_version
  s3_access_bucket_names = var.ec2_ssm_test_clone_s3_bucket_names
}

output "ec2_ssm_test_instance_id" {
  description = "SSM-enabled test instance ID."
  value       = module.ec2_ssm_test.instance_id
}

output "ec2_ssm_test_private_ip" {
  description = "Private IP of the SSM test instance."
  value       = module.ec2_ssm_test.private_ip
}

output "ec2_ssm_test_subnet_id" {
  description = "Subnet selected for the SSM test instance."
  value       = module.ec2_ssm_test.subnet_id
}

output "ec2_ssm_test_clone_instance_id" {
  description = "Second SSM jumpbox instance ID when ec2_ssm_test_clone_enabled is true; null otherwise."
  value       = var.ec2_ssm_test_clone_enabled ? module.ec2_ssm_test_clone[0].instance_id : null
}

output "ec2_ssm_test_clone_private_ip" {
  description = "Private IP of the clone jumpbox when enabled; null otherwise."
  value       = var.ec2_ssm_test_clone_enabled ? module.ec2_ssm_test_clone[0].private_ip : null
}

output "ec2_ssm_test_clone_subnet_id" {
  description = "Subnet of the clone jumpbox (matches primary when enabled); null otherwise."
  value       = var.ec2_ssm_test_clone_enabled ? module.ec2_ssm_test_clone[0].subnet_id : null
}

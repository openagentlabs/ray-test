# -----------------------------------------------------------------------------
# Windows Server 2022 EC2 test instance with SSM Session Manager and Fleet Manager
# Remote Desktop prep (user_data). Uses the same IAM instance profile and security group
# as module ec2_ssm_test (Ubuntu jumpbox i-0342e59b40cd01082) so EKS and NLB/ALB paths match.
# Subnet defaults to the same subnet as ec2_ssm_test unless ec2_ssm_windows_test_subnet_id is set.
# -----------------------------------------------------------------------------

locals {
  ec2_ssm_windows_test_subnet_id_effective = var.ec2_ssm_windows_test_subnet_id != "" ? var.ec2_ssm_windows_test_subnet_id : module.ec2_ssm_test.subnet_id
}

module "ec2_ssm_windows_test" {
  count  = var.ec2_ssm_windows_test_enabled ? 1 : 0
  source = "./modules/ec2-ssm-windows-test"

  aws_account_id      = var.aws_account_id
  environment         = var.environment
  aws_region          = var.aws_region
  vpc_id              = var.eks_vpc_id
  subnet_id           = local.ec2_ssm_windows_test_subnet_id_effective
  instance_type       = var.ec2_ssm_windows_test_instance_type
  root_volume_size_gb = var.ec2_ssm_windows_test_root_volume_size_gb

  shared_jumpbox_security_group_id     = module.ec2_ssm_test.security_group_id
  shared_jumpbox_instance_profile_name = module.ec2_ssm_test.iam_instance_profile_name
  enable_eks_kubectl_iam               = false
  bootstrap_install_eks_cli            = true
  eks_cluster_name                     = module.eks.eks_cluster_name
  eks_kubernetes_version               = module.eks.eks_cluster_version
  enable_fleet_manager_bootstrap       = true

  key_name = local.ec2_ssm_windows_test_key_pair_effective ? aws_key_pair.ec2_ssm_windows_test[0].key_name : ""
}

output "ec2_ssm_windows_test_instance_id" {
  description = "Windows SSM test instance ID (null when ec2_ssm_windows_test_enabled is false)."
  value       = try(module.ec2_ssm_windows_test[0].instance_id, null)
}

output "ec2_ssm_windows_test_private_ip" {
  description = "Private IP of the Windows SSM test instance."
  value       = try(module.ec2_ssm_windows_test[0].private_ip, null)
}

output "ec2_ssm_windows_test_subnet_id" {
  description = "Subnet used by the Windows SSM test instance."
  value       = try(module.ec2_ssm_windows_test[0].subnet_id, null)
}

output "ec2_ssm_windows_test_vpc_id" {
  description = "VPC containing the Windows test instance (matches eks_vpc_id when the module is enabled)."
  value       = try(module.ec2_ssm_windows_test[0].vpc_id, null)
}

output "ec2_ssm_windows_test_connect_hint" {
  description = "How to open Session Manager or Fleet Manager Remote Desktop on the Windows instance."
  value = var.ec2_ssm_windows_test_enabled ? format(
    "Fleet Manager RDP: Systems Manager > Fleet Manager > Managed nodes > select midas-*-ec2-ssm-windows-test > Node actions > Connect > Remote Desktop (your IAM user needs ssm-guiconnect:StartConnection and related). PowerShell: EC2 > Instances > Connect > Session Manager. After first boot, run aws eks update-kubeconfig --name %s --region us-east-1.",
    module.eks.eks_cluster_name,
  ) : null
}

output "ec2_ssm_windows_test_key_pair_name" {
  description = "EC2 key pair name when ec2_ssm_windows_test_key_pair_enabled is true; null otherwise."
  value       = length(aws_key_pair.ec2_ssm_windows_test) > 0 ? aws_key_pair.ec2_ssm_windows_test[0].key_name : null
}

output "ec2_ssm_windows_test_private_key_path" {
  description = "Expected host path to the manual private PEM (repo keypair/midas-windows-dev-local.pem) when key pair is enabled; null otherwise. File is gitignored and must exist on the operator machine for GetPasswordData decrypt."
  value       = local.ec2_ssm_windows_test_key_pair_effective ? "${path.root}/../../keypair/midas-windows-dev-local.pem" : null
}

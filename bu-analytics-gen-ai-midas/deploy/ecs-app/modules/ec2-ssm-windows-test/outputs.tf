output "instance_id" {
  description = "EC2 instance ID."
  value       = aws_instance.windows_ssm_test.id
}

output "private_ip" {
  description = "Primary private IPv4 address."
  value       = aws_instance.windows_ssm_test.private_ip
}

output "subnet_id" {
  description = "Subnet ID used by the instance."
  value       = var.subnet_id
}

output "vpc_id" {
  description = "VPC ID (must match var.vpc_id; echoed from subnet data for convenience)."
  value       = data.aws_subnet.selected.vpc_id
}

output "availability_zone" {
  description = "AZ of the subnet."
  value       = data.aws_subnet.selected.availability_zone
}

output "security_group_id" {
  description = "Security group attached to the instance (shared jumpbox SG when shared_jumpbox_* inputs are set)."
  value       = local.use_shared_jumpbox ? var.shared_jumpbox_security_group_id : aws_security_group.this[0].id
}

output "iam_role_name" {
  description = "IAM role name behind the instance profile (shared jumpbox role when shared_jumpbox_* inputs are set)."
  value       = local.use_shared_jumpbox ? data.aws_iam_instance_profile.shared_jumpbox[0].role_name : aws_iam_role.ec2_ssm_windows[0].name
}

output "iam_role_arn" {
  description = "IAM role ARN (same as ec2-ssm-test when using shared instance profile)."
  value       = local.use_shared_jumpbox ? data.aws_iam_instance_profile.shared_jumpbox[0].role_arn : aws_iam_role.ec2_ssm_windows[0].arn
}

output "ami_id" {
  description = "Amazon Windows Server 2022 Base AMI used at apply time."
  value       = data.aws_ssm_parameter.windows_2022_base.value
}

output "uses_shared_ec2_ssm_test_identity" {
  description = "True when this instance uses the Ubuntu jumpbox security group and instance profile."
  value       = local.use_shared_jumpbox
}

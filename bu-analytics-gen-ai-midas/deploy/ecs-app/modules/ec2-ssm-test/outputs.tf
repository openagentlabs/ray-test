output "instance_id" {
  description = "EC2 instance ID."
  value       = aws_instance.this.id
}

output "private_ip" {
  description = "Primary private IPv4 address."
  value       = aws_instance.this.private_ip
}

output "subnet_id" {
  description = "Subnet ID used by the instance."
  value       = local.resolved_subnet_id
}

output "availability_zone" {
  description = "AZ of the selected subnet."
  value       = data.aws_subnet.selected.availability_zone
}

output "security_group_id" {
  description = "Security group attached to the instance."
  value       = aws_security_group.this.id
}

output "iam_role_name" {
  description = "IAM role name attached via instance profile (SSM)."
  value       = aws_iam_role.ec2_ssm.name
}

output "iam_role_arn" {
  description = "IAM role ARN (for EKS access entries and IAM references)."
  value       = aws_iam_role.ec2_ssm.arn
}

output "iam_instance_profile_name" {
  description = "Instance profile name attached to the SSM jump box (share with other EC2 in the same VPC for identical IAM)."
  value       = aws_iam_instance_profile.ec2_ssm.name
}

output "subnet_ids" {
  description = "Public and private subnet IDs for the EKS control plane."
  value       = concat(local.public_subnet_ids, aws_subnet.private[*].id)
}

output "fargate_subnet_ids" {
  description = "Private subnet IDs for EKS Fargate profiles."
  value       = aws_subnet.private[*].id
}

output "vpc_id" {
  description = "VPC id for EKS workloads."
  value       = local.vpc_id
}

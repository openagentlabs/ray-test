output "alb_public_subnet_ids" {
  description = "Public subnet IDs for internet-facing Application Load Balancers."
  value       = local.alb_public_subnet_ids
}

output "bastion_subnet_ids" {
  description = "Private subnet IDs for bastion / break-glass hosts (SSM Session Manager)."
  value       = local.bastion_subnet_ids
}

output "eks_private_subnet_ids" {
  description = "Private subnet IDs for EKS Fargate workloads."
  value       = local.eks_private_subnet_ids
}

output "fargate_subnet_ids" {
  description = "Alias for eks_private_subnet_ids — private subnets for EKS Fargate profiles."
  value       = local.eks_private_subnet_ids
}

output "nat_gateway_ids" {
  description = "NAT gateway IDs provisioned for private subnet egress."
  value       = aws_nat_gateway.this[*].id
}

output "subnet_ids" {
  description = "All subnet IDs used by the EKS control plane (ALB public + EKS private)."
  value       = concat(local.alb_public_subnet_ids, local.eks_private_subnet_ids)
}

output "vpc_cidr_block" {
  description = "CIDR block of the platform VPC."
  value       = local.use_existing ? data.aws_vpc.selected[0].cidr_block : aws_vpc.this[0].cidr_block
}

output "vpc_endpoints_security_group_id" {
  description = "Security group attached to interface VPC endpoints (empty when endpoints disabled)."
  value       = try(aws_security_group.vpc_endpoints[0].id, "")
}

output "vpc_id" {
  description = "Platform VPC ID."
  value       = local.vpc_id
}

data "aws_vpc" "selected" {
  count = local.use_existing ? 1 : 0
  id    = var.existing_vpc_id
}

output "alb_security_group_id" {
  description = "Security group for internet-facing Application Load Balancers."
  value       = aws_security_group.alb.id
}

output "bastion_security_group_id" {
  description = "Security group for bastion hosts (SSM Session Manager; optional SSH)."
  value       = aws_security_group.bastion.id
}

output "eks_cluster_security_group_id" {
  description = "Security group for the EKS cluster control plane."
  value       = aws_security_group.eks_cluster.id
}

output "eks_workloads_security_group_id" {
  description = "Security group for EKS Fargate workload ENIs."
  value       = aws_security_group.eks_workloads.id
}

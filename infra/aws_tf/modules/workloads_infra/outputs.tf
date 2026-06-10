output "cluster_arn" {
  description = "EKS cluster ARN."
  value       = module.eks_platform.cluster_arn
}

output "cluster_certificate_authority_data" {
  description = "Base64-encoded CA certificate for the EKS API."
  value       = module.eks_platform.cluster_certificate_authority_data
}

output "cluster_endpoint" {
  description = "EKS API server endpoint."
  value       = module.eks_platform.cluster_endpoint
}

output "cluster_name" {
  description = "EKS cluster name."
  value       = module.eks_platform.cluster_name
}

output "control_plane_log_group_name" {
  description = "CloudWatch log group for EKS control plane logs."
  value       = module.eks_platform.control_plane_log_group_name
}

output "eks_cloudwatch_dashboard_arn" {
  description = "CloudWatch dashboard ARN for EKS metrics and logs."
  value       = module.eks_cloudwatch.dashboard_arn
}

output "eks_cloudwatch_dashboard_name" {
  description = "CloudWatch dashboard name for EKS metrics and logs."
  value       = module.eks_cloudwatch.dashboard_name
}

output "eks_containers_log_group_name" {
  description = "CloudWatch log group for Fargate container stdout/stderr."
  value       = module.eks_cloudwatch.eks_containers_log_group_name
}

output "container_insights_log_group_names" {
  description = "Container Insights log groups for the EKS cluster."
  value       = module.eks_cloudwatch.container_insights_log_group_names
}

output "k8s_namespace" {
  description = "Kubernetes namespace for ARB workloads."
  value       = module.eks_platform.namespace
}

output "oidc_provider_arn" {
  description = "IAM OIDC provider ARN for IRSA."
  value       = module.eks_platform.oidc_provider_arn
}

output "oidc_provider_url" {
  description = "OIDC issuer host (without https://) for IRSA trust policies."
  value       = module.eks_platform.oidc_provider_url
}

output "subnet_ids" {
  description = "VPC subnet IDs used by the EKS cluster."
  value       = module.vpc.subnet_ids
}

output "vpc_id" {
  description = "VPC ID hosting the EKS cluster."
  value       = module.vpc.vpc_id
}

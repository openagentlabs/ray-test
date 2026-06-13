output "fargate_pod_execution_role_arn" {
  description = "IAM role ARN for Fargate pod execution (image pull, logging)."
  value       = aws_iam_role.fargate_pod_execution.arn
}

output "fargate_pod_execution_role_name" {
  description = "IAM role name for Fargate pod execution."
  value       = aws_iam_role.fargate_pod_execution.name
}

output "control_plane_log_group_name" {
  description = "CloudWatch log group for EKS control plane logs."
  value       = aws_cloudwatch_log_group.control_plane.name
}

output "cluster_arn" {
  description = "EKS cluster ARN."
  value       = aws_eks_cluster.this.arn
}

output "cluster_certificate_authority_data" {
  description = "Base64-encoded CA certificate for the cluster API."
  value       = aws_eks_cluster.this.certificate_authority[0].data
}

output "cluster_endpoint" {
  description = "EKS API server endpoint."
  value       = aws_eks_cluster.this.endpoint
}

output "cluster_name" {
  description = "EKS cluster name."
  value       = aws_eks_cluster.this.name
}

output "namespace" {
  description = "Kubernetes namespace for ARB workloads."
  value       = var.namespace
}

output "oidc_provider_arn" {
  description = "IAM OIDC provider ARN for IRSA."
  value       = aws_iam_openid_connect_provider.cluster.arn
}

output "oidc_provider_url" {
  description = "OIDC issuer host (without https://) for IRSA trust policies."
  value       = replace(aws_eks_cluster.this.identity[0].oidc[0].issuer, "https://", "")
}

output "cluster_security_group_id" {
  description = "EKS-managed primary security group attached to cluster ENIs and EC2 nodes."
  value       = aws_eks_cluster.this.vpc_config[0].cluster_security_group_id
}

output "cluster_service_ipv4_cidr" {
  description = "Kubernetes service IPv4 CIDR for nodeadm bootstrap on AL2023 Ray nodes."
  value       = aws_eks_cluster.this.kubernetes_network_config[0].service_ipv4_cidr
}

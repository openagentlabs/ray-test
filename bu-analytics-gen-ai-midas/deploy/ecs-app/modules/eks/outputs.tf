output "eks_cluster_name" {
  description = "EKS cluster name"
  value       = aws_eks_cluster.this.name
}

output "eks_cluster_version" {
  description = "EKS control plane Kubernetes version (e.g. 1.30) for client tooling alignment"
  value       = aws_eks_cluster.this.version
}

output "eks_cluster_arn" {
  description = "EKS cluster ARN"
  value       = aws_eks_cluster.this.arn
}

output "eks_cluster_endpoint" {
  description = "Kubernetes API endpoint (private only when endpoint_public_access is false)"
  value       = aws_eks_cluster.this.endpoint
}

output "eks_cluster_certificate_authority_data" {
  description = "Base64 CA data for kubeconfig"
  value       = aws_eks_cluster.this.certificate_authority[0].data
  sensitive   = true
}

output "eks_node_group_name" {
  description = "Managed node group name"
  value       = aws_eks_node_group.this.node_group_name
}

output "eks_cluster_security_group_id" {
  description = "EKS-managed cluster security group (control plane / node wiring)"
  value       = aws_eks_cluster.this.vpc_config[0].cluster_security_group_id
}

output "eks_node_role_arn" {
  description = "IAM role ARN for EC2 nodes"
  value       = aws_iam_role.node.arn
}

output "eks_node_role_name" {
  description = "IAM role name for EC2 nodes (for aws_iam_role_policy.role)"
  value       = aws_iam_role.node.name
}

output "oidc_issuer_url" {
  description = "EKS OIDC issuer URL for IRSA (aws_iam_openid_connect_provider / AssumeRoleWithWebIdentity)."
  value       = aws_eks_cluster.this.identity[0].oidc[0].issuer
}

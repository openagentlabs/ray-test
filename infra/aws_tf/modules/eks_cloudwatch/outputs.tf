output "cloudwatch_observability_role_arn" {
  description = "IRSA role ARN for the amazon-cloudwatch-observability EKS addon."
  value       = aws_iam_role.cloudwatch_observability.arn
}

output "dashboard_name" {
  description = "CloudWatch dashboard name for EKS cluster metrics and logs."
  value       = aws_cloudwatch_dashboard.eks.dashboard_name
}

output "dashboard_arn" {
  description = "CloudWatch dashboard ARN."
  value       = aws_cloudwatch_dashboard.eks.dashboard_arn
}

output "eks_containers_log_group_name" {
  description = "CloudWatch log group for Fargate container stdout/stderr (platform)."
  value       = aws_cloudwatch_log_group.eks_containers.name
}

output "eks_control_plane_log_group_name" {
  description = "CloudWatch log group for EKS control plane logs (managed by eks_platform)."
  value       = local.eks_control_plane_log_group
}

output "container_insights_log_group_names" {
  description = "Container Insights log groups created for the cluster."
  value = {
    application = aws_cloudwatch_log_group.container_insights_application.name
    performance = aws_cloudwatch_log_group.container_insights_performance.name
    dataplane   = aws_cloudwatch_log_group.container_insights_dataplane.name
  }
}

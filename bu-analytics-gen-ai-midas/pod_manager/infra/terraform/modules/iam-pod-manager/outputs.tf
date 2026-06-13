output "role_arn" {
  description = "IAM role ARN for IRSA (annotate the Kubernetes service account)."
  value       = aws_iam_role.pod_manager.arn
}

output "role_name" {
  description = "IAM role name."
  value       = aws_iam_role.pod_manager.name
}

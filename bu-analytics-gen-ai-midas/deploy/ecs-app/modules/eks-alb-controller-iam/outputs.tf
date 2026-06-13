output "oidc_provider_arn" {
  description = "ARN of the IAM OIDC identity provider for the cluster."
  value       = aws_iam_openid_connect_provider.eks.arn
}

output "aws_load_balancer_controller_role_arn" {
  description = "IAM role ARN for IRSA (Helm: serviceAccount.annotations eks.amazonaws.com/role-arn)."
  value       = aws_iam_role.aws_load_balancer_controller.arn
}

output "aws_load_balancer_controller_policy_arn" {
  description = "Managed IAM policy ARN attached to the controller role."
  value       = aws_iam_policy.aws_load_balancer_controller.arn
}

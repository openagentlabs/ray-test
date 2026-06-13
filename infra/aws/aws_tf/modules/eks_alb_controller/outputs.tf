output "alb_controller_iam_role_arn" {
  description = "IAM role ARN assumed by the AWS Load Balancer Controller via IRSA."
  value       = aws_iam_role.alb_controller.arn
}

output "alb_controller_iam_role_name" {
  description = "IAM role name for the AWS Load Balancer Controller."
  value       = aws_iam_role.alb_controller.name
}

output "helm_release_name" {
  description = "Helm release name for the AWS Load Balancer Controller."
  value       = helm_release.aws_load_balancer_controller.name
}

output "helm_release_status" {
  description = "Helm release status for the AWS Load Balancer Controller."
  value       = helm_release.aws_load_balancer_controller.status
}

output "ingress_class" {
  description = "IngressClass name workloads should use for ALB-backed Ingress resources."
  value       = var.ingress_class
}

output "service_account_name" {
  description = "Kubernetes service account name for the AWS Load Balancer Controller."
  value       = local.service_account_name
}

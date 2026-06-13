output "aws_region" {
  value = var.aws_region
}

output "aws_account_id" {
  value = data.aws_caller_identity.current.account_id
}

output "deploy_target" {
  value = local.deploy_target
}

output "service_name" {
  description = "Service name prefix (must match Helm / app_config)."
  value       = var.service_name
}

output "cluster_name" {
  value = module.eks.cluster_name
}

output "cluster_endpoint" {
  value = module.eks.cluster_endpoint
}

output "vpc_id" {
  value = local.vpc_id
}

output "private_subnet_ids" {
  value = local.private_subnet_ids
}

output "ecr_repository_urls" {
  description = "Push container images here before helm upgrade."
  value       = module.ecr.repository_urls
}

output "pod_manager_irsa_role_arn" {
  description = "Set routing-tier.serviceAccount.roleArn in Helm values."
  value       = module.iam_pod_manager.role_arn
}

output "alb_controller_role_arn" {
  value = module.eks_alb_controller.role_arn
}

output "db_table_prefix" {
  description = "Routing-tier Postgres table prefix (must match Helm podManager.postgres.tablePrefix)."
  value       = var.db_table_prefix
}

output "helm_set_flags" {
  description = "Helm --set flags aligning IRSA, service_name, and Postgres table prefix with Terraform."
  value       = local.helm_set_flags
}

output "helm_values_snippet" {
  description = "Deprecated alias for helm_set_flags."
  value       = local.helm_set_flags
}

output "kubeconfig_command" {
  value = "aws eks update-kubeconfig --region ${var.aws_region} --name ${module.eks.cluster_name}"
}

output "cluster_arn" {
  description = "ECS cluster ARN."
  value       = aws_ecs_cluster.this.arn
}

output "cluster_name" {
  description = "ECS cluster name."
  value       = aws_ecs_cluster.this.name
}

output "execution_role_arn" {
  description = "IAM role ARN for ECS task execution (image pull, logs)."
  value       = aws_iam_role.execution.arn
}

output "service_discovery_namespace_id" {
  description = "Cloud Map private DNS namespace id."
  value       = aws_service_discovery_private_dns_namespace.this.id
}

output "service_discovery_namespace_name" {
  description = "Cloud Map private DNS namespace (suffix for service hostnames)."
  value       = aws_service_discovery_private_dns_namespace.this.name
}

output "subnet_ids" {
  description = "Public subnet ids for Fargate tasks."
  value       = var.subnet_ids
}

output "task_security_group_id" {
  description = "Security group shared by ECS tasks in this stack."
  value       = aws_security_group.tasks.id
}

output "vpc_id" {
  description = "VPC id for ECS workloads."
  value       = var.vpc_id
}

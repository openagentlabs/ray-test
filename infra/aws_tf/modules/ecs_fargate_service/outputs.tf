output "cloudwatch_log_group_name" {
  description = "CloudWatch log group for this ECS task."
  value       = aws_cloudwatch_log_group.task.name
}

output "discovery_dns_name" {
  description = "Private DNS hostname for this service within the Cloud Map namespace."
  value       = "${var.service_discovery_name}.${var.service_discovery_namespace_name}"
}

output "ecs_service_name" {
  description = "ECS service name."
  value       = aws_ecs_service.this.name
}

output "load_balancer_dns_name" {
  description = "Public ALB DNS name when enable_public_alb is true; empty otherwise."
  value       = var.enable_public_alb ? aws_lb.public[0].dns_name : ""
}

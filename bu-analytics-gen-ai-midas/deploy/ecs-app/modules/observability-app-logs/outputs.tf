output "backend_application_log_group_name" {
  description = "CloudWatch Log Group name for backend application logs. Pass to Helm as observability.logGroupName."
  value       = aws_cloudwatch_log_group.backend_application.name
}

output "backend_application_log_group_arn" {
  description = "CloudWatch Log Group ARN (use in Fluent Bit / CW Agent IAM policies)."
  value       = aws_cloudwatch_log_group.backend_application.arn
}

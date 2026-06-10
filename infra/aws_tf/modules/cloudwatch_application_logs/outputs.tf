output "log_group_arns_by_key" {
  description = "Map of service key (e.g. frontend) to CloudWatch log group ARN."
  value       = { for k, g in aws_cloudwatch_log_group.service : k => g.arn }
}

output "log_group_names_by_key" {
  description = "Map of service key to log group name (set CLOUDWATCH_LOG_GROUP_NAME per workload)."
  value       = { for k, g in aws_cloudwatch_log_group.service : k => g.name }
}

output "application_logs_put_policy_arn" {
  description = "Attach this IAM policy to roles used by workloads that call logs:PutLogEvents."
  value       = aws_iam_policy.application_logs_put.arn
}

output "application_logs_put_policy_name" {
  description = "IAM policy name for application CloudWatch Logs delivery."
  value       = aws_iam_policy.application_logs_put.name
}

output "service_identity_by_key" {
  description = "Stable service.id and service.name for each log group (set OTEL_SERVICE_NAME / OTEL_SERVICE_INSTANCE_ID)."
  value = {
    for k, meta in local.services : k => {
      service_id   = meta.id
      service_name = meta.name
    }
  }
}

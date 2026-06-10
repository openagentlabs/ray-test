output "topic_arn" {
  description = "ARN of the SNS topic used by notification.svc (set app_config.toml `[sns].topic_arn`)."
  value       = aws_sns_topic.notifications.arn
}

output "topic_name" {
  description = "Name of the SNS notifications topic."
  value       = aws_sns_topic.notifications.name
}

output "email_subscription_arns" {
  description = "Map of email endpoint → subscription ARN (pending until the recipient confirms)."
  value       = { for k, v in aws_sns_topic_subscription.email : k => v.arn }
}

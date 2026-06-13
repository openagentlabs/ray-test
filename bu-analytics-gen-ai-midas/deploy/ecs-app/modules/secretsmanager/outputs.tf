output "app_secret_id" {
  description = "Secrets Manager secret ID (same as name for this secret)."
  value       = aws_secretsmanager_secret.app.id
}

output "app_secret_arn" {
  description = "ARN of the MIDAS application Secrets Manager secret."
  value       = aws_secretsmanager_secret.app.arn
}

output "app_secret_name" {
  description = "Friendly name of the MIDAS application secret."
  value       = aws_secretsmanager_secret.app.name
}

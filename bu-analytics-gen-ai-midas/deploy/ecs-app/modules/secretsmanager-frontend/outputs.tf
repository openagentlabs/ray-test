output "frontend_secret_id" {
  description = "Secrets Manager secret ID (same as name: midas-{env}-{region}/frontend)."
  value       = aws_secretsmanager_secret.frontend.id
}

output "frontend_secret_arn" {
  description = "ARN of the MIDAS frontend Secrets Manager secret."
  value       = aws_secretsmanager_secret.frontend.arn
}

output "frontend_secret_name" {
  description = "Friendly name of the MIDAS frontend secret."
  value       = aws_secretsmanager_secret.frontend.name
}

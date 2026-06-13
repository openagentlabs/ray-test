output "secret_id" {
  description = "Secret ID (same as name for this secret)."
  value       = aws_secretsmanager_secret.test_001.id
}

output "secret_arn" {
  description = "ARN of the test secret."
  value       = aws_secretsmanager_secret.test_001.arn
}

output "secret_name" {
  description = "Secret name."
  value       = aws_secretsmanager_secret.test_001.name
}

output "db_instance_identifier" {
  description = "RDS instance identifier."
  value       = aws_db_instance.postgres.id
}

output "db_instance_endpoint" {
  description = "PostgreSQL endpoint (hostname)."
  value       = aws_db_instance.postgres.address
}

output "db_instance_port" {
  description = "PostgreSQL port."
  value       = aws_db_instance.postgres.port
}

output "db_name" {
  description = "Database name."
  value       = aws_db_instance.postgres.db_name
}

output "db_master_user_secret_arn" {
  description = "Secrets Manager ARN for the master user (when manage_master_user_password is true)."
  value       = try(aws_db_instance.postgres.master_user_secret[0].secret_arn, null)
}

output "db_security_group_id" {
  description = "Security group ID for the RDS instance."
  value       = aws_security_group.postgres.id
}

output "db_subnet_group_name" {
  description = "DB subnet group name."
  value       = aws_db_subnet_group.postgres.name
}

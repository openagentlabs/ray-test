output "replication_group_id" {
  description = "ElastiCache replication group ID."
  value       = aws_elasticache_replication_group.redis.id
}

output "primary_endpoint_address" {
  description = "Primary endpoint address (hostname) for Redis."
  value       = aws_elasticache_replication_group.redis.primary_endpoint_address
}

output "reader_endpoint_address" {
  description = "Reader endpoint address (when num_cache_clusters > 1)."
  value       = aws_elasticache_replication_group.redis.reader_endpoint_address
}

output "port" {
  description = "Redis port (TLS)."
  value       = aws_elasticache_replication_group.redis.port
}

output "redis_security_group_id" {
  description = "Security group ID for the replication group."
  value       = aws_security_group.redis.id
}

output "subnet_group_name" {
  description = "ElastiCache subnet group name."
  value       = aws_elasticache_subnet_group.redis.name
}

output "redis_auth_secret_arn" {
  description = "Secrets Manager ARN for the Redis auth secret (JSON with redis_url, password, host, port, ssl)."
  value       = aws_secretsmanager_secret.redis_auth.arn
}

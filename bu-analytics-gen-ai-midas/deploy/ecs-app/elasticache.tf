# -----------------------------------------------------------------------------
# ElastiCache Redis (module: ./modules/elasticache).
# Same registration pattern as deploy/ecs-app/rds.tf.
# VPC and subnets match EKS: vpc_id = eks_vpc_id; subnets = effective EKS node subnets.
# -----------------------------------------------------------------------------

module "elasticache_redis" {
  count  = var.elasticache_redis_enabled ? 1 : 0
  source = "./modules/elasticache"

  aws_account_id = var.aws_account_id
  environment    = var.environment
  aws_region     = var.aws_region

  vpc_id                        = var.eks_vpc_id
  subnet_ids                    = local.elasticache_subnet_ids_effective
  eks_cluster_security_group_id = module.eks.eks_cluster_security_group_id

  engine_version                         = var.elasticache_redis_engine_version
  node_type                              = var.elasticache_redis_node_type
  num_cache_clusters                     = var.elasticache_redis_num_cache_clusters
  secretsmanager_recovery_window_in_days = var.secretsmanager_recovery_window_in_days

  additional_ingress_cidrs_all_traffic = var.elasticache_additional_ingress_cidrs_all_traffic
}

output "elasticache_redis_primary_endpoint" {
  description = "Redis primary endpoint (empty if elasticache_redis_enabled is false)."
  value       = var.elasticache_redis_enabled ? module.elasticache_redis[0].primary_endpoint_address : null
}

output "elasticache_redis_reader_endpoint" {
  description = "Redis reader endpoint when num_cache_clusters > 1."
  value       = var.elasticache_redis_enabled ? module.elasticache_redis[0].reader_endpoint_address : null
}

output "elasticache_redis_port" {
  description = "Redis port (TLS)."
  value       = var.elasticache_redis_enabled ? module.elasticache_redis[0].port : null
}

output "elasticache_redis_replication_group_id" {
  description = "ElastiCache replication group ID."
  value       = var.elasticache_redis_enabled ? module.elasticache_redis[0].replication_group_id : null
}

output "elasticache_redis_security_group_id" {
  description = "ElastiCache Redis security group ID."
  value       = var.elasticache_redis_enabled ? module.elasticache_redis[0].redis_security_group_id : null
}

output "elasticache_redis_auth_secret_arn" {
  description = "Secrets Manager ARN for the Redis AUTH token."
  value       = var.elasticache_redis_enabled ? module.elasticache_redis[0].redis_auth_secret_arn : null
}

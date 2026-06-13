resource "aws_elasticache_subnet_group" "exlerate_redis_sng" {
  name       = "exlerate-redc-subnet-group-${var.environment}"
  subnet_ids = local.eks_subnet_ids

  lifecycle {
    ignore_changes = [subnet_ids]
  }
}

# ---------------------------
# Langfuse Redis Cluster
# ---------------------------
resource "aws_elasticache_replication_group" "langfuse_redis_cluster" {
  replication_group_id = "${var.eks_cluster_name}-langfuse"
  description          = "Langfuse Redis Cluster"
  engine               = "redis"
  node_type            = var.redis_node_type

  num_cache_clusters         = var.redis_cache_nodes
  automatic_failover_enabled = true
  multi_az_enabled           = true

  subnet_group_name  = aws_elasticache_subnet_group.exlerate_redis_sng.name
  security_group_ids = [aws_security_group.exlerate_langfuse_redis_cluster.id]

  transit_encryption_enabled = true
  at_rest_encryption_enabled = true
}

# Random DB passwords
resource "random_password" "langfuse_redis_db_password" {
  length  = 16
  special = false
}

resource "aws_elasticache_user" "langfuse_user" {
  user_id       = "langfuse-user-${var.environment}"
  user_name     = "langfuse-user-${var.environment}"
  access_string = "on ~* +@all"
  engine        = "redis"
  passwords     = [random_password.langfuse_redis_db_password.result]
}

resource "aws_elasticache_user_group" "langfuse_group" {
  engine        = "redis"
  user_group_id = "langfuse-group-${var.environment}"
  user_ids = [
    "default",
    aws_elasticache_user.langfuse_user.user_id
  ]
}

# ---------------------------
# Inference Redis Cluster
# ---------------------------
resource "aws_elasticache_replication_group" "inference_redis_cluster" {
  replication_group_id = "${var.eks_cluster_name}-inference"
  description          = "Inference Redis Cluster"
  engine               = "redis"
  node_type            = var.redis_node_type

  num_cache_clusters         = var.redis_cache_nodes
  automatic_failover_enabled = true
  multi_az_enabled           = true

  subnet_group_name  = aws_elasticache_subnet_group.exlerate_redis_sng.name
  security_group_ids = [aws_security_group.exlerate_langfuse_redis_cluster.id]

  transit_encryption_enabled = true
  at_rest_encryption_enabled = true
}


# Random DB passwords
resource "random_password" "inference_redis_db_password" {
  length  = 16
  special = false
}

resource "aws_elasticache_user" "inference_user" {
  user_id       = "inference-user-${var.environment}"
  user_name     = "inference-user-${var.environment}"
  access_string = "on ~* +@all"
  engine        = "redis"
  passwords     = [random_password.inference_redis_db_password.result]
}

resource "aws_elasticache_user_group" "inference_group" {
  engine        = "redis"
  user_group_id = "inference-group-${var.environment}"
  user_ids = [
    "default",
    aws_elasticache_user.inference_user.user_id
  ]
}
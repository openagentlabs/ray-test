# MIDAS ElastiCache Redis - private, encrypted in transit and at rest; same VPC/subnets as EKS nodes.
# Register in deploy/ecs-app/elasticache.tf

locals {
  name_prefix = "midas-${var.environment}-${var.aws_region}"
  # replication_group_id: lowercase alphanumeric + hyphens, max 40 chars
  replication_group_id = "midas-${var.environment}-redis"
  common_tags = merge(
    {
      Name        = "${local.name_prefix}-redis"
      Purpose     = "midas-elasticache-redis"
      Environment = var.environment
      AccountId   = var.aws_account_id
      ManagedBy   = "Terraform"
    },
    var.tags,
  )
}

data "aws_subnet" "cache" {
  for_each = toset(var.subnet_ids)
  id       = each.value
}

resource "aws_elasticache_subnet_group" "redis" {
  name       = "${local.name_prefix}-redis-subnets"
  subnet_ids = var.subnet_ids
  tags       = merge(local.common_tags, { Name = "${local.name_prefix}-redis-subnets" })

  lifecycle {
    precondition {
      condition = alltrue([
        for id in var.subnet_ids : data.aws_subnet.cache[id].vpc_id == var.vpc_id
      ])
      error_message = "Every subnet_ids entry must belong to vpc_id."
    }
    precondition {
      condition = length(distinct([
        for id in var.subnet_ids : data.aws_subnet.cache[id].availability_zone
      ])) >= 2
      error_message = "ElastiCache subnet group requires subnets in at least 2 Availability Zones (match EKS node subnets spanning 2 AZs)."
    }
  }
}

resource "aws_security_group" "redis" {
  name_prefix = "${local.name_prefix}-redis-"
  description = "Redis from EKS cluster security group only"
  vpc_id      = var.vpc_id

  tags = merge(local.common_tags, { Name = "${local.name_prefix}-redis-sg" })

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_security_group_rule" "redis_from_eks_cluster_sg" {
  description              = "Redis from EKS cluster/worker ENIs"
  type                     = "ingress"
  from_port                = 6379
  to_port                  = 6379
  protocol                 = "tcp"
  source_security_group_id = var.eks_cluster_security_group_id
  security_group_id        = aws_security_group.redis.id
}

# Optional cross-network / admin access (all protocols) - see var.additional_ingress_cidrs_all_traffic
resource "aws_security_group_rule" "redis_additional_all_traffic" {
  for_each = toset(var.additional_ingress_cidrs_all_traffic)

  description       = "All traffic from approved CIDR (${each.value})"
  type              = "ingress"
  from_port         = 0
  to_port           = 0
  protocol          = "-1"
  cidr_blocks       = [each.value]
  security_group_id = aws_security_group.redis.id
}

resource "random_password" "redis_auth" {
  length  = 32
  special = false
}

resource "aws_secretsmanager_secret" "redis_auth" {
  name_prefix             = "${local.name_prefix}-redis-auth-"
  recovery_window_in_days = var.secretsmanager_recovery_window_in_days

  tags = merge(local.common_tags, { Name = "${local.name_prefix}-redis-auth" })

  lifecycle {
    ignore_changes = [recovery_window_in_days]
  }
}

resource "aws_secretsmanager_secret_version" "redis_auth" {
  secret_id = aws_secretsmanager_secret.redis_auth.id
  # Store as JSON so the backend's build_redis_url_from_secret_dict can resolve a
  # valid redis_url directly. The raw password alone is not a valid redis:// URL.
  secret_string = jsonencode({
    redis_url = "rediss://:${random_password.redis_auth.result}@${aws_elasticache_replication_group.redis.primary_endpoint_address}:${aws_elasticache_replication_group.redis.port}/0"
    password  = random_password.redis_auth.result
    host      = aws_elasticache_replication_group.redis.primary_endpoint_address
    port      = aws_elasticache_replication_group.redis.port
    ssl       = true
  })

  lifecycle {
    ignore_changes = [secret_string]
  }
}

resource "aws_elasticache_replication_group" "redis" {
  replication_group_id = local.replication_group_id
  description          = "MIDAS Redis ${var.environment} (same VPC/subnets as EKS)"

  engine             = "redis"
  engine_version     = var.engine_version
  node_type          = var.node_type
  num_cache_clusters = var.num_cache_clusters
  port               = 6379

  subnet_group_name  = aws_elasticache_subnet_group.redis.name
  security_group_ids = [aws_security_group.redis.id]

  at_rest_encryption_enabled = true
  transit_encryption_enabled = true
  auth_token                 = random_password.redis_auth.result

  automatic_failover_enabled = var.num_cache_clusters > 1
  multi_az_enabled           = var.num_cache_clusters > 1

  snapshot_retention_limit = 0
  apply_immediately        = true

  tags = local.common_tags

  lifecycle {
    precondition {
      condition     = length(random_password.redis_auth.result) >= 16
      error_message = "Redis auth token must be at least 16 characters."
    }
  }
}

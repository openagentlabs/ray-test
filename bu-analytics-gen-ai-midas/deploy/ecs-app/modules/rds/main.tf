# MIDAS PostgreSQL RDS - private, encrypted, dev-oriented defaults.
# Register in deploy/ecs-app/rds.tf. Subnets/VPC match EKS (see root module inputs).

locals {
  name_prefix = "midas-${var.environment}-${var.aws_region}"
  common_tags = merge(
    {
      Name        = "${local.name_prefix}-postgres"
      Purpose     = "midas-postgres-development"
      Environment = var.environment
      AccountId   = var.aws_account_id
      ManagedBy   = "Terraform"
    },
    var.tags,
  )
}

data "aws_subnet" "db" {
  for_each = toset(var.db_subnet_ids)
  id       = each.value
}

resource "aws_db_subnet_group" "postgres" {
  name_prefix = "${local.name_prefix}-pg-"
  subnet_ids  = var.db_subnet_ids
  tags        = merge(local.common_tags, { Name = "${local.name_prefix}-pg-subnets" })

  lifecycle {
    precondition {
      condition = alltrue([
        for id in var.db_subnet_ids : data.aws_subnet.db[id].vpc_id == var.vpc_id
      ])
      error_message = "Every db_subnet_ids entry must belong to vpc_id."
    }
  }
}

resource "aws_security_group" "postgres" {
  name_prefix = "${local.name_prefix}-pg-"
  description = "PostgreSQL - EKS cluster SG, optional VPC CIDR / jump CIDRs, optional extra client SGs"
  vpc_id      = var.vpc_id

  tags = merge(local.common_tags, { Name = "${local.name_prefix}-pg-sg" })

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_security_group_rule" "postgres_from_eks_cluster_sg" {
  description              = "PostgreSQL from EKS cluster/worker ENIs"
  type                     = "ingress"
  from_port                = 5432
  to_port                  = 5432
  protocol                 = "tcp"
  source_security_group_id = var.eks_cluster_security_group_id
  security_group_id        = aws_security_group.postgres.id
}

# Optional cross-network / admin access (all protocols) - see var.additional_ingress_cidrs_all_traffic
resource "aws_security_group_rule" "postgres_additional_all_traffic" {
  for_each = toset(var.additional_ingress_cidrs_all_traffic)

  description       = "All traffic from approved CIDR (${each.value})"
  type              = "ingress"
  from_port         = 0
  to_port           = 0
  protocol          = "-1"
  cidr_blocks       = [each.value]
  security_group_id = aws_security_group.postgres.id
}

resource "aws_security_group_rule" "postgres_additional_tcp_5432_cidr" {
  for_each = toset(var.additional_ingress_cidrs_tcp_5432)

  description       = "PostgreSQL from approved CIDR (${each.value})"
  type              = "ingress"
  from_port         = 5432
  to_port           = 5432
  protocol          = "tcp"
  cidr_blocks       = [each.value]
  security_group_id = aws_security_group.postgres.id
}

resource "aws_security_group_rule" "postgres_additional_tcp_5432_from_sg" {
  for_each = toset(var.additional_source_security_group_ids_tcp_5432)

  description              = "PostgreSQL from approved security group (${each.value})"
  type                     = "ingress"
  from_port                = 5432
  to_port                  = 5432
  protocol                 = "tcp"
  source_security_group_id = each.value
  security_group_id        = aws_security_group.postgres.id
}

# Fortify "Insufficient RDS Monitoring": IAM role that RDS assumes to publish
# enhanced monitoring metrics to CloudWatch. Created only when enhanced
# monitoring is enabled (var.monitoring_interval > 0).
data "aws_iam_policy_document" "rds_monitoring_assume" {
  count = var.monitoring_interval > 0 ? 1 : 0
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["monitoring.rds.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "rds_monitoring" {
  count              = var.monitoring_interval > 0 ? 1 : 0
  name_prefix        = "${local.name_prefix}-rds-mon-"
  assume_role_policy = data.aws_iam_policy_document.rds_monitoring_assume[0].json
  tags               = local.common_tags
}

resource "aws_iam_role_policy_attachment" "rds_monitoring" {
  count      = var.monitoring_interval > 0 ? 1 : 0
  role       = aws_iam_role.rds_monitoring[0].name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonRDSEnhancedMonitoringRole"
}

resource "aws_db_instance" "postgres" {
  identifier_prefix = "${local.name_prefix}-pg-"

  engine               = "postgres"
  engine_version       = var.engine_version
  instance_class       = var.instance_class
  allocated_storage    = var.allocated_storage
  storage_type         = "gp3"
  storage_encrypted                   = true
  iam_database_authentication_enabled = true
  db_subnet_group_name                = aws_db_subnet_group.postgres.name
  vpc_security_group_ids = [
    aws_security_group.postgres.id,
  ]

  db_name  = var.db_name
  username = var.master_username

  manage_master_user_password = true

  publicly_accessible     = false
  copy_tags_to_snapshot   = true
  backup_retention_period = var.backup_retention_period
  backup_window           = "03:00-05:00"
  maintenance_window      = "sun:05:00-sun:06:00"
  auto_minor_version_upgrade = true

  multi_az            = false
  deletion_protection = var.deletion_protection
  skip_final_snapshot = var.skip_final_snapshot
  apply_immediately   = true

  # Fortify "Insufficient RDS Monitoring": enhanced monitoring + performance insights.
  monitoring_interval = var.monitoring_interval
  monitoring_role_arn = var.monitoring_interval > 0 ? aws_iam_role.rds_monitoring[0].arn : null

  performance_insights_enabled          = var.performance_insights_enabled
  performance_insights_retention_period = var.performance_insights_enabled ? var.performance_insights_retention_period : null
  performance_insights_kms_key_id       = var.performance_insights_enabled && var.performance_insights_kms_key_id != "" ? var.performance_insights_kms_key_id : null

  enabled_cloudwatch_logs_exports = ["postgresql", "upgrade"]

  tags = local.common_tags

  lifecycle {
    precondition {
      condition = length(distinct([
        for id in var.db_subnet_ids : data.aws_subnet.db[id].availability_zone
      ])) >= 2
      error_message = "RDS requires subnets in at least 2 Availability Zones for the subnet group (match EKS node subnets spanning 2 AZs)."
    }
  }
}

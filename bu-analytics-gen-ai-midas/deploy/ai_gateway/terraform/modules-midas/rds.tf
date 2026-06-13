#################################
#     LiteLLM RDS
#################################

resource "aws_db_instance" "rds_pg_eks_db" {
  identifier            = "exlerate-rds-pg-${var.eks_cluster_name}-litellm"
  engine                = "postgres"
  engine_version        = var.db_engine_version
  instance_class        = var.instance_class
  allocated_storage     = var.rds_alloc_storage
  max_allocated_storage = var.max_alloc_storage
  storage_type          = "gp3"

  db_name                 = var.litellm_rds_db_name
  username                = var.lite_db_username
  password                = aws_secretsmanager_secret_version.pg_db_password_value.secret_string
  storage_encrypted                   = true
  iam_database_authentication_enabled = true
  vpc_security_group_ids  = [aws_security_group.exlerate_rds_db_sg.id]
  multi_az                = false
  db_subnet_group_name    = aws_db_subnet_group.exlerate_db_sng.name
  backup_retention_period = 30
  skip_final_snapshot     = var.skip_final_snapshot_flag

  deletion_protection = var.deletion_protection

  copy_tags_to_snapshot = true
  # Fortify "RDS Auto-Upgrade Disabled" remediation: minor versions deliver
  # security patches; control the apply window via maintenance_window below.
  auto_minor_version_upgrade = true
  maintenance_window         = "sun:06:00-sun:07:00"

  monitoring_interval = 60
  monitoring_role_arn = aws_iam_role.rds_enhanced_monitoring.arn

  performance_insights_enabled          = true
  performance_insights_retention_period = 7
  performance_insights_kms_key_id       = aws_kms_key.rds_performance_insights_kms_key.arn

  enabled_cloudwatch_logs_exports = ["postgresql", "upgrade"]

  depends_on = [
    aws_security_group.exlerate_rds_db_sg
  ]
}

resource "aws_db_subnet_group" "exlerate_db_sng" {
  name       = "exlerate-db-subnet-group-${var.environment}"
  subnet_ids = local.eks_subnet_ids

  lifecycle {
    ignore_changes = [subnet_ids]
  }
}

#################################
#     Langfuse RDS
#################################

resource "aws_db_instance" "rds_pg_eks_db_langfuse" {
  identifier            = "exlerate-rds-pg-${var.eks_cluster_name}-langfuse"
  engine                = "postgres"
  engine_version        = var.db_engine_version
  instance_class        = var.instance_class
  allocated_storage     = var.rds_alloc_storage
  max_allocated_storage = var.max_alloc_storage
  storage_type          = "gp3"

  db_name                 = var.langfuse_rds_db_name
  username                = var.lang_db_username
  password                = aws_secretsmanager_secret_version.langfuse_pg_db_password_value.secret_string
  storage_encrypted                   = true
  iam_database_authentication_enabled = true
  vpc_security_group_ids  = [aws_security_group.exlerate_rds_db_sg.id]
  multi_az                = false
  db_subnet_group_name    = aws_db_subnet_group.exlerate_db_sng.name
  backup_retention_period = 30
  skip_final_snapshot     = var.skip_final_snapshot_flag

  deletion_protection = var.deletion_protection

  copy_tags_to_snapshot = true
  # Fortify "RDS Auto-Upgrade Disabled" remediation: minor versions deliver
  # security patches; control the apply window via maintenance_window below.
  auto_minor_version_upgrade = true
  maintenance_window         = "sun:06:00-sun:07:00"

  monitoring_interval = 60
  monitoring_role_arn = aws_iam_role.rds_enhanced_monitoring.arn

  performance_insights_enabled          = true
  performance_insights_retention_period = 7
  performance_insights_kms_key_id       = aws_kms_key.rds_performance_insights_kms_key.arn

  enabled_cloudwatch_logs_exports = ["postgresql", "upgrade"]

  depends_on = [
    aws_security_group.exlerate_rds_db_sg
  ]
}

#################################
#     C1 API RDS
#################################
resource "aws_db_instance" "rds_pg_eks_db_c1_api" {
  identifier            = "exlerate-rds-pg-${var.eks_cluster_name}-c1-api"
  engine                = "postgres"
  engine_version        = var.db_engine_version
  instance_class        = var.instance_class
  allocated_storage     = var.rds_alloc_storage
  max_allocated_storage = var.max_alloc_storage
  storage_type          = "gp3"

  db_name                 = var.c1_api_rds_db_name
  username                = var.c1_api_db_username
  password                = aws_secretsmanager_secret_version.c1_api_pg_db_password_value.secret_string
  storage_encrypted                   = true
  iam_database_authentication_enabled = true
  vpc_security_group_ids  = [aws_security_group.exlerate_rds_db_sg.id]
  multi_az                = false
  db_subnet_group_name    = aws_db_subnet_group.exlerate_db_sng.name
  backup_retention_period = 30
  skip_final_snapshot     = var.skip_final_snapshot_flag

  deletion_protection = var.deletion_protection

  copy_tags_to_snapshot = true
  # Fortify "RDS Auto-Upgrade Disabled" remediation: minor versions deliver
  # security patches; control the apply window via maintenance_window below.
  auto_minor_version_upgrade = true
  maintenance_window         = "sun:06:00-sun:07:00"

  monitoring_interval = 60
  monitoring_role_arn = aws_iam_role.rds_enhanced_monitoring.arn

  performance_insights_enabled          = true
  performance_insights_retention_period = 7
  performance_insights_kms_key_id       = aws_kms_key.rds_performance_insights_kms_key.arn

  enabled_cloudwatch_logs_exports = ["postgresql", "upgrade"]

  depends_on = [
    aws_security_group.exlerate_rds_db_sg
  ]
}
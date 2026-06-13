resource "aws_cloudwatch_log_group" "exelerate_cw_group" {
  name              = var.log_group_name
  retention_in_days = 7
  skip_destroy      = false
  kms_key_id        = aws_kms_key.cloudwatch_kms_key.arn
}

resource "aws_cloudwatch_log_stream" "exelerate_cw_group_ls" {
  name           = var.log_group_name
  log_group_name = aws_cloudwatch_log_group.exelerate_cw_group.name
}

resource "aws_cloudwatch_metric_alarm" "rds_high_cpu_litellm" {
  alarm_name          = "${var.eks_cluster_name}-rds-high-cpu-litellm"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "CPUUtilization"
  namespace           = "AWS/RDS"
  period              = 300
  statistic           = "Average"
  threshold           = 80

  dimensions = {
    DBInstanceIdentifier = aws_db_instance.rds_pg_eks_db.id
  }
}

resource "aws_cloudwatch_metric_alarm" "rds_high_cpu_langfuse" {
  alarm_name          = "${var.eks_cluster_name}-rds-high-cpu-langfuse"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "CPUUtilization"
  namespace           = "AWS/RDS"
  period              = 300
  statistic           = "Average"
  threshold           = 80

  dimensions = {
    DBInstanceIdentifier = aws_db_instance.rds_pg_eks_db_langfuse.id
  }
}
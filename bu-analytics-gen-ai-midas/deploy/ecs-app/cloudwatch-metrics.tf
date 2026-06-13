# -----------------------------------------------------------------------------
# CloudWatch resources for MIDAS application custom metrics.
#
# Metric delivery path (direct PutMetricData - no log-based metric filter):
#
#   Python heartbeat thread (keith_log_matrics_test.py)
#     +- boto3 put_metric_data()
#          +- CloudWatch (routed via shared VPC owner's existing endpoints)
#               +- CloudWatch Custom Metric
#                    Namespace : MIDAS/Training
#                    Metric    : keith_kets_training_value
#                    Dimensions: operation / service / environment
#
# Logging path (unchanged - managed separately):
#   Backend pod stdout  ->  /midas/{env}/backend  (CloudWatch Logs)
#   No metric filter is used; logs and metrics are independent pipelines.
#
# Deployment path: Jenkins -> terraform apply (never run locally against shared envs).
# Related: backend/app/services/keith_log_matrics_test.py
#          deploy/ecs-app/eks-node-cloudwatch-metrics.tf  (node role IAM)
# Note: VPC endpoint for CloudWatch is managed by the VPC owner account (shared VPC);
#       no vpc-endpoints.tf is required here.
# -----------------------------------------------------------------------------

# -----------------------------------------------------------------------------
# CloudWatch Metric Alarm - fires when no training heartbeat arrives for 3 min.
#
# SampleCount < 1 over 3 x 60 s means no PutMetricData call received for 3
# consecutive minutes, indicating the training process may be hung or the pod
# may have restarted unexpectedly.
# treat_missing_data = "breaching" so silence is itself treated as a breach
# (correct behaviour for a liveness heartbeat alarm).
# -----------------------------------------------------------------------------
resource "aws_cloudwatch_metric_alarm" "keith_kets_no_heartbeat" {
  alarm_name          = "midas-${var.environment}-keith-kets-no-heartbeat"
  alarm_description   = "MIDAS training heartbeat (keith_kets_training_value) not received for 3 minutes. Training process may be hung or pod may have restarted."
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = 3
  metric_name         = "keith_kets_training_value"
  namespace           = "MIDAS/Training"
  period              = 60
  statistic           = "SampleCount"
  threshold           = 1
  treat_missing_data  = "breaching"

  tags = {
    Environment = var.environment
    ManagedBy   = "terraform"
    Project     = "midas"
  }
}

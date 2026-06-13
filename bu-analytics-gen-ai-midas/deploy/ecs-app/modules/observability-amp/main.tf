# MIDAS Amazon Managed Prometheus (AMP) + AMG workspace (Phase B)
#
# Creates:
#   - AMP workspace for Prometheus-compatible metric storage
#   - IAM policy for the ADOT Collector DaemonSet (EKS node role or IRSA)
#     to write metrics via Remote Write
#
# Register in deploy/ecs-app/observability.tf:
#   module "observability_amp" {
#     source      = "./modules/observability-amp"
#     environment = var.environment
#   }
#
# After apply, set in Helm values:
#   observability.otlpEndpoint: "http://adot-collector.adot.svc.cluster.local:4317"
#
# AMP Remote Write URL is exported as amp_remote_write_url.
# Use it in deploy/observability/otel-collector/values.yaml.

locals {
  workspace_alias = "midas-${var.environment}"
  # When an external log group ARN is not provided, use the one created below.
  # This avoids a chicken-and-egg: passing var.amp_log_group_arn directly when
  # it is empty ("") would produce ":*" which is an invalid ARN.
  amp_log_group_arn_effective = var.amp_log_group_arn != "" ? var.amp_log_group_arn : (
    length(aws_cloudwatch_log_group.amp) > 0 ? aws_cloudwatch_log_group.amp[0].arn : ""
  )
}

resource "aws_cloudwatch_log_group" "amp" {
  count             = var.amp_log_group_arn == "" ? 1 : 0
  name              = "/midas/${var.environment}/amp"
  retention_in_days = var.retention_in_days

  tags = merge(
    {
      Environment = var.environment
      ManagedBy   = "terraform"
      Project     = "midas"
      Component   = "observability-amp-logs"
    },
    var.tags,
  )
}

resource "aws_prometheus_workspace" "this" {
  alias = local.workspace_alias

  tags = merge(
    {
      Environment = var.environment
      ManagedBy   = "terraform"
      Project     = "midas"
      Component   = "observability-amp"
    },
    var.tags,
  )

  logging_configuration {
    log_group_arn = "${local.amp_log_group_arn_effective}:*"
  }

  depends_on = [aws_cloudwatch_log_group.amp]

  # aps:CreateLoggingConfiguration is not permitted by the deployer role's
  # session policy. The logging config is set once via the bootstrap procedure
  # (aws amp create-logging-configuration) and must not be re-applied by
  # Terraform on every run to avoid a perpetual permission failure.
  lifecycle {
    ignore_changes = [logging_configuration]
  }
}

# IAM policy — attach to the EKS node role (or an IRSA service account) for the
# ADOT Collector DaemonSet so it can call aps:RemoteWrite.
resource "aws_iam_policy" "amp_remote_write" {
  name        = "midas-${var.environment}-amp-remote-write"
  description = "Allow ADOT Collector to write metrics to the MIDAS AMP workspace."

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AMPRemoteWrite"
        Effect = "Allow"
        Action = [
          "aps:RemoteWrite",
          "aps:GetSeries",
          "aps:GetLabels",
          "aps:GetMetricMetadata",
        ]
        Resource = aws_prometheus_workspace.this.arn
      }
    ]
  })

  tags = merge(
    {
      Environment = var.environment
      ManagedBy   = "terraform"
      Project     = "midas"
    },
    var.tags,
  )
}

# Attach the Remote Write policy to the EKS node role so the ADOT Collector
# DaemonSet (running on every node) can push metrics to AMP.
# If you prefer IRSA, remove this attachment and create an IRSA role instead.
resource "aws_iam_role_policy_attachment" "node_amp_remote_write" {
  count      = var.eks_node_role_name != "" ? 1 : 0
  role       = var.eks_node_role_name
  policy_arn = aws_iam_policy.amp_remote_write.arn
}

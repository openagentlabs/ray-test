# MIDAS backend application CloudWatch Log Group
#
# Creates a dedicated log group for backend application logs.
# The log group name is exported so Jenkins / Helm can inject
# LOG_CLOUDWATCH_LOG_GROUP into the backend pod via:
#   deploy/scripts/helm-deploy-releases.sh --set-string \
#     observability.logGroupName=<backend_application_log_group_name>
#
# Register in deploy/ecs-app/ by adding:
#   module "observability_app_logs" {
#     source      = "./modules/observability-app-logs"
#     environment = var.environment
#     tags        = local.common_tags
#   }

locals {
  log_group_name = "/midas/${var.environment}/backend"
}

resource "aws_cloudwatch_log_group" "backend_application" {
  name              = local.log_group_name
  retention_in_days = var.retention_in_days
  kms_key_id        = var.kms_key_arn != "" ? var.kms_key_arn : null

  tags = merge(
    {
      Environment = var.environment
      ManagedBy   = "terraform"
      Project     = "midas"
      Component   = "backend-application-logs"
    },
    var.tags,
  )
}

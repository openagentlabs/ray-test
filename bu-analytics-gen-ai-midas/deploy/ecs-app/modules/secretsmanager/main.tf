# MIDAS application secret - name matches deploy_role IAM wildcard midas-*.
# No secret version here: avoid storing credentials in Terraform state; use PutSecretValue after apply.

locals {
  name_prefix = "midas-${var.environment}-${var.aws_region}"
}

resource "aws_secretsmanager_secret" "app" {
  name                    = "${local.name_prefix}/app"
  recovery_window_in_days = var.recovery_window_in_days

  lifecycle {
    # Changing recovery_window_in_days forces replacement; ignore drift so edits
    # to the variable do not destroy/recreate the secret (preserves ARN for apps).
    ignore_changes = [recovery_window_in_days]
  }

  tags = {
    Name        = "${local.name_prefix}/app"
    Purpose     = "midas-app-configuration"
    Environment = var.environment
    AccountId   = var.aws_account_id
    ManagedBy   = "Terraform"
  }
}

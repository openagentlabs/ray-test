# -----------------------------------------------------------------------------
# AWS Secrets Manager — test secret midas-test-secret-001 (module: ./modules/secretsmanager-test-secret).
# Default value is set via var.midas_test_secret_001_value (default "hello from keith").
# The value is stored in Terraform state; use for non-production demos only.
# -----------------------------------------------------------------------------

module "secretsmanager_test_secret" {
  source = "./modules/secretsmanager-test-secret"

  aws_account_id          = var.aws_account_id
  environment             = var.environment
  secret_string           = var.midas_test_secret_001_value
  recovery_window_in_days = var.secretsmanager_recovery_window_in_days
}

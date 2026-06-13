# Test/demo secret — name matches deploy_role IAM wildcard midas-*.
# Secret string is managed in Terraform (stored in state); override via root variable
# midas_test_secret_001_value.

resource "aws_secretsmanager_secret" "test_001" {
  name                    = var.secret_name
  recovery_window_in_days = var.recovery_window_in_days

  lifecycle {
    ignore_changes = [recovery_window_in_days]
  }

  tags = {
    Name        = var.secret_name
    Purpose     = "midas-test-secret-demo"
    Environment = var.environment
    AccountId   = var.aws_account_id
    ManagedBy   = "Terraform"
  }
}

resource "aws_secretsmanager_secret_version" "test_001" {
  secret_id     = aws_secretsmanager_secret.test_001.id
  secret_string = var.secret_string
}

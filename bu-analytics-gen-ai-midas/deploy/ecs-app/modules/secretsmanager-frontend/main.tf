# MIDAS frontend configuration secret — name: midas-{environment}-{region}/frontend.
#
# Seeded by Terraform on first apply from the Cognito + VITE_* variables passed
# into this module.  All VITE_* values are non-sensitive (they are baked into the
# public JS bundle by Vite at Docker build time), so storing them here is safe.
#
# lifecycle.ignore_changes on secret_string ensures Terraform never overwrites
# the secret once it has been set — CI scripts or manual updates take precedence.
#
# Re-seed after a Cognito change:
#   1. Remove the lifecycle.ignore_changes block temporarily (or use -target).
#   2. terraform apply -var-file=tfvars/<env>.tfvars
#   3. Restore lifecycle.ignore_changes.
#
# If apply fails with ResourceExistsException (secret already in AWS but not in
# Terraform state), import once before apply:
#   terraform import \
#     -var-file=tfvars/midas-cross-network-db-access.tfvars \
#     -var 'aws_account_id=...' -var 'environment=...' \
#     -var 'terraform_state_bucket=...' \
#     'module.secretsmanager_frontend.aws_secretsmanager_secret.frontend' \
#     'midas-<env>-<region>/frontend'
# Example dev: ... 'midas-dev-us-east-1/frontend'

locals {
  name_prefix = "midas-${var.environment}-${var.aws_region}"
}

resource "aws_secretsmanager_secret" "frontend" {
  name                    = "${local.name_prefix}/frontend"
  recovery_window_in_days = var.recovery_window_in_days

  lifecycle {
    # Changing recovery_window_in_days forces replacement; ignore drift so edits
    # to the variable do not destroy/recreate the secret (preserves ARN for consumers).
    ignore_changes = [recovery_window_in_days]
  }

  tags = {
    Name        = "${local.name_prefix}/frontend"
    Purpose     = "midas-frontend-configuration"
    Environment = var.environment
    AccountId   = var.aws_account_id
    ManagedBy   = "Terraform"
  }
}

# Seed the secret with the Cognito + VITE_* values required by the React app.
# All VITE_* variables are non-sensitive (they end up in the public JS bundle).
#
# lifecycle.ignore_changes prevents Terraform from reverting manual or CI updates
# after the first apply (e.g. when the Docker build injects updated values).
#
# Validation rules (enforced via variable blocks in variables.tf):
#   VITE_COGNITO_DOMAIN         — https:// prefix, no trailing slash
#   VITE_COGNITO_CLIENT_ID      — lowercase alphanumeric Cognito client ID (deployed env client)
#   VITE_COGNITO_REDIRECT_URI   — ends with /auth/callback
#   VITE_COGNITO_LOGOUT_REDIRECT_URI — https:// prefix
#   VITE_BASE_URL               — https:// prefix, no trailing slash
resource "aws_secretsmanager_secret_version" "frontend_seed" {
  secret_id = aws_secretsmanager_secret.frontend.id

  secret_string = jsonencode({
    VITE_COGNITO_DOMAIN              = var.vite_cognito_domain
    VITE_COGNITO_CLIENT_ID           = var.vite_cognito_client_id
    VITE_COGNITO_REDIRECT_URI        = var.vite_cognito_redirect_uri
    VITE_COGNITO_LOGOUT_REDIRECT_URI = var.vite_cognito_logout_redirect_uri
    VITE_COGNITO_SCOPES              = var.vite_cognito_scopes
    VITE_BASE_URL                    = var.vite_base_url
  })

  lifecycle {
    # Do not let Terraform overwrite the secret after the initial seed.
    # CI pipelines and manual updates own the secret content post-deploy.
    ignore_changes = [secret_string]
  }
}

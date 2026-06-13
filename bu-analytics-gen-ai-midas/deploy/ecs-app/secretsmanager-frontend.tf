# -----------------------------------------------------------------------------
# AWS Secrets Manager - frontend configuration secret (module: ./modules/secretsmanager-frontend).
# Creates midas-{environment}-{region}/frontend and seeds it with the Cognito +
# VITE_* values required by the React app at Docker build time.
#
# The secret version uses lifecycle.ignore_changes so Terraform never reverts
# keys added or updated after the first apply (CI pipelines and manual updates
# own the content post-deploy).
#
# To re-seed after a Cognito change, see modules/secretsmanager-frontend/main.tf.
#
# If apply fails with ResourceExistsException (secret already exists in AWS but
# not in Terraform state), import once after init:
#   terraform import \
#     -var-file=tfvars/midas-cross-network-db-access.tfvars \
#     -var 'aws_account_id=...' -var 'environment=...' \
#     -var 'terraform_state_bucket=...' \
#     'module.secretsmanager_frontend.aws_secretsmanager_secret.frontend' \
#     'midas-<env>-<region>/frontend'
# Example dev: ... 'midas-dev-us-east-1/frontend'
# -----------------------------------------------------------------------------

module "secretsmanager_frontend" {
  source = "./modules/secretsmanager-frontend"

  aws_account_id          = var.aws_account_id
  environment             = var.environment
  aws_region              = var.aws_region
  recovery_window_in_days = var.secretsmanager_recovery_window_in_days

  # Cognito + frontend base-URL — seeded into the SM secret on first apply.
  # Values are validated in modules/secretsmanager-frontend/variables.tf.
  vite_cognito_domain              = var.frontend_vite_cognito_domain
  vite_cognito_client_id           = var.frontend_vite_cognito_client_id
  vite_cognito_redirect_uri        = var.frontend_vite_cognito_redirect_uri
  vite_cognito_logout_redirect_uri = var.frontend_vite_cognito_logout_redirect_uri
  vite_cognito_scopes              = var.frontend_vite_cognito_scopes
  vite_base_url                    = var.frontend_vite_base_url
}

output "secretsmanager_frontend_secret_arn" {
  description = "ARN of the MIDAS frontend Secrets Manager secret (midas-{env}-us-east-1/frontend)."
  value       = module.secretsmanager_frontend.frontend_secret_arn
}

output "secretsmanager_frontend_secret_name" {
  description = "Friendly name of the MIDAS frontend Secrets Manager secret."
  value       = module.secretsmanager_frontend.frontend_secret_name
}

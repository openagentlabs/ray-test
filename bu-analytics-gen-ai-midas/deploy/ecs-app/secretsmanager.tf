# -----------------------------------------------------------------------------
# AWS Secrets Manager - application configuration secret (module: ./modules/secretsmanager).
# Same registration pattern as deploy/ecs-app/s3.tf.
# Secret value: by default Terraform also seeds an initial SecretString (RDS wiring
# + region keys); see secretsmanager-app-secret-version.tf and variable
# secretsmanager_app_secret_seed_from_rds. Merge additional keys with
# deploy/scripts/ci/populate-secrets.sh (it merges with existing SM JSON by default).
#
# Do not toggle recovery_window_in_days per env in a way that forces replacement:
# changing it replaces the secret (destroy + create). A destroy with a 7-30 day
# window schedules deletion and blocks reusing the same name until restored or
# the window ends - breaking apply and any consumers until fixed.
#
# If apply fails with ResourceExistsException (secret already exists in AWS but
# not in Terraform state), import once after init/backend (same -var-file / -var
# as terraform plan — required root vars e.g. aws_account_id):
#   terraform import -var-file=tfvars/midas-cross-network-db-access.tfvars \\
#     -var 'aws_account_id=...' -var 'environment=...' -var 'terraform_state_bucket=...' \\
#     'module.secretsmanager.aws_secretsmanager_secret.app' 'midas-<env>-<region>/app'
# Example dev: ... 'midas-dev-us-east-1/app'
# If AWS shows "scheduled for deletion", run deploy/scripts/midas-secretsmanager-app-unstick.sh
# -----------------------------------------------------------------------------

module "secretsmanager" {
  source = "./modules/secretsmanager"

  aws_account_id          = var.aws_account_id
  environment             = var.environment
  aws_region              = var.aws_region
  recovery_window_in_days = var.secretsmanager_recovery_window_in_days
}

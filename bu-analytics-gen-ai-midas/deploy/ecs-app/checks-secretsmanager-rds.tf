# Variable validation cannot reference other variables (Terraform language rule).
# This check preserves the same rule as the former validation block on
# secretsmanager_app_secret_seed_from_rds.

check "secretsmanager_app_secret_seed_requires_rds" {
  assert {
    condition     = !var.secretsmanager_app_secret_seed_from_rds || var.rds_postgres_enabled
    error_message = "secretsmanager_app_secret_seed_from_rds cannot be true when rds_postgres_enabled is false; set secretsmanager_app_secret_seed_from_rds = false."
  }
}

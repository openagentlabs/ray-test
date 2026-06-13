# -----------------------------------------------------------------------------
# Seed midas-{environment}-us-east-1/app SecretString from Terraform.
# Variable: secretsmanager_app_secret_seed_from_rds (variables.tf, default true).
#
# Call chain: Terraform writes string keys here → helm-deploy-releases.sh syncs
# SM JSON → K8s midas-app-secret → envFrom → Python Settings → load_secret_slot
# uses AWS_RDS_POSTGRES_SECRET_ID with AwsSecretsManagerReader.get_secret_value
# on the RDS master secret (second SM object; created by AWS for the RDS
# instance when manage_master_user_password = true in modules/rds).
#
# lifecycle.ignore_changes on secret_string avoids Terraform overwriting a
# larger JSON after populate-secrets.sh merges API keys. If the RDS master ARN
# changes, update midas-.../app manually or temporarily remove ignore_changes.
#
# GRAPHRAG_API_KEY is seeded as an empty string placeholder so the key exists
# in the secret from day one. Set the real value after the first deploy with:
#   ./deploy/scripts/ci/set-graphrag-api-key.sh [ENVIRONMENT]
# The lifecycle.ignore_changes ensures Terraform never overwrites the real key
# once it has been set via that script.
#
# MAX_FILE_SIZE is surfaced as an env var via K8s midas-app-secret (envFrom);
# backend Settings reads os.getenv("MAX_FILE_SIZE") (bytes). 10737418240 = 10 GiB,
# matching the Python default in app/core/config.py.
# -----------------------------------------------------------------------------

resource "aws_secretsmanager_secret_version" "app_seed" {
  # Require RDS when seeding RDS keys (avoids module.rds_postgres[0] when count is 0).
  count = var.secretsmanager_app_secret_seed_from_rds && var.rds_postgres_enabled ? 1 : 0

  secret_id = module.secretsmanager.app_secret_id
  secret_string = jsonencode({
    AWS_RDS_POSTGRES_SECRET_ID = module.rds_postgres[0].db_master_user_secret_arn
    AWS_RDS_POSTGRES_DB_NAME   = module.rds_postgres[0].db_name
    # host and port are seeded so pods can resolve the RDS endpoint even when the
    # RDS-managed secret (after rotation) only contains username/password.
    # The app loader merges these into the SM RDS secret payload before parsing.
    AWS_RDS_POSTGRES_HOST          = module.rds_postgres[0].db_instance_endpoint
    AWS_RDS_POSTGRES_PORT          = "5432"
    AWS_RDS_POSTGRES_SSLMODE       = "require"
    AWS_SECRETS_MANAGER_REGION     = var.aws_region
    AWS_REGION                     = var.aws_region
    AWS_DEFAULT_REGION             = var.aws_region
    AWS_SECRETS_MANAGER_VERIFY_SSL = "false"

    # S3 and Redis configuration
    S3_BUCKET_NAME       = module.s3.test_bucket_id
    S3_REGION            = var.aws_region
    S3_UPLOAD_KEY_PREFIX = "uploads"
    # Upload byte limit for FastAPI Settings.MAX_FILE_SIZE (explicit in SM for ops visibility).
    MAX_FILE_SIZE                  = "10737418240"
    SESSION_ELASTICACHE_SECRET_ARN = module.elasticache_redis[0].redis_auth_secret_arn
    # Placeholder — set the real key after first deploy via set-graphrag-api-key.sh.
    # lifecycle.ignore_changes ensures terraform apply never overwrites the real value.
    GRAPHRAG_API_KEY = ""
  })

  lifecycle {
    ignore_changes = [secret_string]
  }

  depends_on = [
    module.secretsmanager,
    module.rds_postgres,
  ]
}

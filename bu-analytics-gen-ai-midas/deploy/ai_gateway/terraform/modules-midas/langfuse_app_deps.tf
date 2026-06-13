# Langfuse Permission sets and secret defintions
module "langfuse_irsa_permissions_set" {
  source           = "./irsa_blocks"
  eks_cluster_name = var.eks_cluster_name
  application      = var.langfuse_ns

  eks_oidc_url      = local.eks_oidc_url # This only changes if the cluster is redeployed
  eks_namespace     = var.langfuse_ns
  account_id        = data.aws_caller_identity.current.account_id
  irsa_account_name = "langfuse-irsa-account"

  policy_arns = [
    "arn:aws:iam::aws:policy/AmazonSSMReadOnlyAccess",
    "arn:aws:iam::aws:policy/AWSSecretsManagerClientReadOnlyAccess",
    "arn:aws:iam::aws:policy/AmazonS3ReadOnlyAccess",
    "arn:aws:iam::aws:policy/AmazonRDSReadOnlyAccess",
    aws_iam_policy.langfuse_s3_config_policy.arn
  ]
  depends_on = [kubernetes_namespace_v1.langfuse]

}

########################################
# Langfuse secrets mapped to Kubernetes
#########################################
locals {
  langfuse_secret_vals = {
    "db-password"                    = random_password.pg_db_password_langfuse.result,
    "db-endpoint"                    = aws_db_instance.rds_pg_eks_db_langfuse.address,
    "db-name"                        = aws_db_instance.rds_pg_eks_db_langfuse.db_name,
    "event-bucket"                   = aws_s3_bucket.exlerate_langfuse_data_bucket.bucket
    "batch-bucket"                   = aws_s3_bucket.exlerate_langfuse_data_bucket.bucket
    "media-bucket"                   = aws_s3_bucket.exlerate_langfuse_media_bucket.bucket
    "redis-host"                     = aws_elasticache_replication_group.langfuse_redis_cluster.primary_endpoint_address
    "redis-user"                     = "langfuse-user-${var.environment}"
    "redis-password"                 = random_password.langfuse_redis_db_password.result
    "salt-key"                       = data.aws_secretsmanager_secret_version.litellm_salt_key.secret_string
    "next-auth"                      = data.aws_secretsmanager_secret_version.langfuse_next_autg_password.secret_string
    # OSS mode: hardcoded "" — see secrets.tf comment on aws_secretsmanager_secret.langfuse_ee_license_key.
    # Empty env var = MIT-licensed OSS mode. AWS Secrets Manager cannot store "" so we
    # bypass it. Promotion path documented in secrets.tf.
    "langfuse-ee-license"            = ""
    "langfuse-cognito-client-id"     = data.aws_secretsmanager_secret_version.langfuse_cognito_client_id.secret_string
    "langfuse-cognito-client-secret" = data.aws_secretsmanager_secret_version.langfuse_cognito_client_secret.secret_string
  }
}

# Secrets needed by Helm values file rather than passing them in Jenkins file
module "langfuse_helm_chart_secrets" {
  for_each = local.langfuse_secret_vals
  source   = "./k_secrets"

  metadataName = each.key
  secretName   = each.key
  ns           = var.langfuse_ns
  secretValue  = each.value
  depends_on   = [kubernetes_namespace_v1.langfuse]
}

locals {
  db_url = "postgresql://${replace("langfuse_admin", ":", "%3A")}:${replace(random_password.pg_db_password_langfuse.result, "@", "%40")}@${aws_db_instance.rds_pg_eks_db_langfuse.address}:5432/${aws_db_instance.rds_pg_eks_db_langfuse.db_name}"
}

resource "kubernetes_secret_v1" "langfuse_postgresql" {
  metadata {
    name      = "langfuse-postgresql-${var.environment}"
    namespace = var.langfuse_ns

    # Helm ownership labels note if uninstalling the chart this secret needs to be reapplied
    labels = {
      "app.kubernetes.io/managed-by" = "Helm"
    }
    # Helm ownership annotations
    annotations = {
      "meta.helm.sh/release-name"      = var.langfuse_ns
      "meta.helm.sh/release-namespace" = var.langfuse_ns
    }
  }
  data = {
    host         = aws_db_instance.rds_pg_eks_db_langfuse.address
    username     = "langfuse_admin"
    password     = random_password.pg_db_password_langfuse.result
    database     = aws_db_instance.rds_pg_eks_db_langfuse.db_name
    DATABASE_URL = local.db_url
  }

  type = "Opaque"

  lifecycle {
    ignore_changes = [
      metadata[0].labels,
      metadata[0].annotations
    ]
  }
  depends_on = [kubernetes_namespace_v1.langfuse]
}


resource "kubernetes_secret_v1" "langfuse_clickhouse_credentials" {
  metadata {
    name      = "clickhouse-credentials-${var.environment}"
    namespace = var.langfuse_ns

    # Helm ownership labels note if uninstalling the chart this secret needs to be reapplied
    labels = {
      "app.kubernetes.io/managed-by" = "Helm"
    }
    # Helm ownership annotations
    annotations = {
      "meta.helm.sh/release-name"      = var.langfuse_ns
      "meta.helm.sh/release-namespace" = var.langfuse_ns
    }
  }

  data = {
    password      = random_password.ch_langfuse_password.result
    url           = "https://default:${random_password.ch_langfuse_password.result}@${var.ch_host}:8123" #was 9000/default
    migration-url = "clickhouse://default:${random_password.ch_langfuse_password.result}@${var.ch_host}:9000/default"
  }

  type       = "Opaque"
  depends_on = [kubernetes_namespace_v1.langfuse]
}

resource "kubernetes_config_map_v1" "langfuse_config_alb_config" {
  metadata {
    name      = "langfuse-alb-config"
    namespace = var.langfuse_ns
  }
  data = {
    SUBNETS      = join(",", var.alb_subnets)
    ACM_CERT_ARN = aws_acm_certificate.langfuse_cert.arn
    AWS_ALB_SG   = aws_security_group.exlerate_langfuse_alb_sg.id
  }
  depends_on = [kubernetes_namespace_v1.langfuse]
}
# LiteLLM Permission sets and secret defintions
module "litellm_irsa_permissions_set" {
  source           = "./irsa_blocks"
  eks_cluster_name = var.eks_cluster_name
  application      = "litellm"

  eks_oidc_url      = local.eks_oidc_url # This only changes if the cluster is redeployed
  eks_namespace     = var.litellm_ns
  account_id        = data.aws_caller_identity.current.account_id
  irsa_account_name = var.irsa_account_name

  policy_arns = [
    "arn:aws:iam::aws:policy/AmazonSSMReadOnlyAccess",
    "arn:aws:iam::aws:policy/AWSSecretsManagerClientReadOnlyAccess",
    "arn:aws:iam::aws:policy/AmazonS3ReadOnlyAccess",
    "arn:aws:iam::aws:policy/AmazonRDSReadOnlyAccess",
    aws_iam_policy.litellm_s3_config_policy.arn
  ]
  depends_on = [kubernetes_namespace_v1.litellm]
}

# Map the secrets to kubernetes to be picked up by helm later
locals {
  secret_vals = {
    "litellm-master-key"        = data.aws_secretsmanager_secret_version.litellm_master_key.secret_string,
    "litellm-salt-key"          = data.aws_secretsmanager_secret_version.litellm_salt_key.secret_string,
    # OSS mode: hardcoded "" — see secrets.tf comment on aws_secretsmanager_secret.litellm_license.
    # Empty env var = LiteLLM community mode (master-key auth only). AWS Secrets Manager
    # cannot store "" so we bypass it. Promotion path documented in secrets.tf.
    "litellm-license"           = "",
    "langfuse-public-key"       = data.aws_secretsmanager_secret_version.langfuse_public_key.secret_string,
    "langfuse-secret-key"       = data.aws_secretsmanager_secret_version.LANGFUSE_SECRET_KEY.secret_string,
    "langfuse-host"             = data.aws_secretsmanager_secret_version.LANGFUSE_HOST.secret_string,
    "azure-openai-api-key"      = data.aws_secretsmanager_secret_version.AZURE_OPENAI_API_KEY.secret_string,
    "azure-openai-api-key-use2" = data.aws_secretsmanager_secret_version.AZURE_OPENAI_API_KEY_EASTUS2.secret_string,
    "vertexai-credentials-json" = data.aws_secretsmanager_secret_version.VERTEXAI_CREDENTIALS_JSON_REF.secret_string,
    "db-password"               = random_password.pg_db_password.result,
    "db-endpoint"               = aws_db_instance.rds_pg_eks_db.address,
    "db-name"                   = aws_db_instance.rds_pg_eks_db.db_name
  }
}

# Secrets needed by Helm values file rather than passing them in Jenkins file
module "litellm_helm_chart_secrets" {
  for_each     = local.secret_vals
  source       = "./k_secrets"
  metadataName = each.key
  secretName   = each.key
  ns           = var.litellm_ns
  secretValue  = each.value
  depends_on   = [kubernetes_namespace_v1.litellm]
}

# ConfigMap needed for LiteLLM to point to S3 config.yaml.
# By default the helm chart generates litellm-config
# But what we're doing is injecting the desired models from S3 after startup
resource "kubernetes_config_map_v1" "litellm_config" {
  metadata {
    name      = "litellm-config-from-s3"
    namespace = var.litellm_ns
  }
  data = {
    AWS_REGION_NAME                  = var.region
    LITELLM_CONFIG_BUCKET_NAME       = aws_s3_bucket.exlerate_config_bucket.id
    LITELLM_CONFIG_BUCKET_OBJECT_KEY = "config.yaml"
  }
  depends_on = [kubernetes_namespace_v1.litellm]
}

resource "kubernetes_config_map_v1" "litellm_config_alb_config" {
  count = local.current.enable_lb ? 1 : 0
  metadata {
    name      = "litellm-alb-config"
    namespace = var.litellm_ns
  }
  data = {
    SUBNETS      = join(",", var.alb_subnets)
    ACM_CERT_ARN = aws_acm_certificate.litellm_cert.arn
    AWS_ALB_SG   = aws_security_group.exlerate_litellm_alb_sg.id
  }
  depends_on = [kubernetes_namespace_v1.litellm]
}

# This resource manifest basically tells the namespace what secrets to fetch
resource "kubernetes_manifest" "aws_ssm_secrets_for_litellm" {
  count = var.bootstrap_phase >= 2 ? 1 : 0
  manifest = {
    apiVersion = "secrets-store.csi.x-k8s.io/v1"
    kind       = "SecretProviderClass"
    metadata = {
      name      = var.sec_provider_class # This is whats referenced in the SPC attribute in the Pod manifest
      namespace = var.litellm_ns
    }
    spec = {
      provider = "aws"
      parameters = {
        objects = <<-EOT
- objectName: ${aws_secretsmanager_secret.litellm_master_key.name}
  objectType: secretsmanager
  objectAlias: "${aws_secretsmanager_secret.litellm_master_key.name}"
  region: ${var.region}
- objectName: ${aws_secretsmanager_secret.litellm_salt_key.name}
  objectType: secretsmanager
  region: ${var.region}
- objectName: ${aws_secretsmanager_secret.litellm_license.name}
  objectType: secretsmanager
  region: ${var.region}
- objectName: ${aws_secretsmanager_secret.langfuse_public_key.name}
  objectType: secretsmanager
  region: ${var.region}
- objectName: ${aws_secretsmanager_secret.LANGFUSE_SECRET_KEY.name}
  objectType: secretsmanager
  region: ${var.region}
- objectName: ${aws_secretsmanager_secret.LANGFUSE_HOST.name}
  objectType: secretsmanager
  region: ${var.region}
- objectName: ${aws_secretsmanager_secret.AZURE_OPENAI_API_KEY.name}
  objectType: secretsmanager
  region: ${var.region}
- objectName: ${aws_secretsmanager_secret.AZURE_OPENAI_API_KEY_EASTUS2.name}
  objectType: secretsmanager
  region: ${var.region}
- objectName: ${aws_secretsmanager_secret.VERTEXAI_CREDENTIALS_JSON.name}
  objectType: secretsmanager
  objectAlias: "${aws_secretsmanager_secret.VERTEXAI_CREDENTIALS_JSON.name}"
  region: ${var.region}
EOT
      }
    }
  }
  depends_on = [module.litellm_irsa_permissions_set,
  kubernetes_namespace_v1.litellm]
}
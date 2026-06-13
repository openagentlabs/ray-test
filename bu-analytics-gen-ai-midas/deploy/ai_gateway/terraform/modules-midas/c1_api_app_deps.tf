# LiteLLM Permission sets and secret defintions
module "c1_api_irsa_permissions_set" {
  source           = "./irsa_blocks"
  eks_cluster_name = var.eks_cluster_name
  application      = "c1-api"

  eks_oidc_url      = local.eks_oidc_url # This only changes if the cluster is redeployed
  eks_namespace     = var.c1_api_ns
  account_id        = data.aws_caller_identity.current.account_id
  irsa_account_name = "c1-api-irsa-account"

  policy_arns = [
    "arn:aws:iam::aws:policy/AmazonSSMReadOnlyAccess",
    "arn:aws:iam::aws:policy/AWSSecretsManagerClientReadOnlyAccess",
    "arn:aws:iam::aws:policy/AmazonRDSReadOnlyAccess",
  ]
  depends_on = [kubernetes_namespace_v1.c1_api]
}

################################################
#   Secrets stored in K8
################################################

# Map the secrets to kubernetes to be picked up by helm later
locals {
  c1_api_secret_vals = {
    "litellm-api-key"     = data.aws_secretsmanager_secret_version.litellm_master_key.secret_string,
    "langfuse-public-key" = data.aws_secretsmanager_secret_version.langfuse_org_public_key_value.secret_string,
    "langfuse-secret-key" = data.aws_secretsmanager_secret_version.langfuse_org_secret_key_value.secret_string,
  }
}

# Secrets needed by Helm values file rather than passing them in Jenkins file
module "c1_api_helm_chart_secrets" {
  for_each     = local.c1_api_secret_vals
  source       = "./k_secrets"
  metadataName = each.key
  secretName   = each.key
  ns           = var.c1_api_ns
  secretValue  = each.value
  depends_on   = [kubernetes_namespace_v1.c1_api]
}

# -----------------------------------------------------------------------------
# langfuse-org-keys
#
# The upstream control-api Helm chart's deployment template hard-codes a volume
# mount for a SINGLE combined Secret named `langfuse-org-keys` with data keys
# `public_key` + `secret_key`. Langfuse's own chart (ORD4), however, publishes
# the two values as SEPARATE Secrets (`langfuse-public-key`, `langfuse-secret-key`).
#
# Until 2026-04-20 this mismatch was bridged imperatively inside
# `Jenkinsfile_ORD6_control_api` via a `kubectl create secret` stage.  Moving
# it here (IaC) means:
#   * the secret is declarative and its state tracked by Terraform,
#   * ORD6 stops being dependent on `kubectl` behavior for its success, and
#   * ORD1 can be run independently end-to-end without ORD6 having to patch
#     things up afterwards.
#
# Values come directly from the AWS Secrets Manager data sources already used
# by the split Secrets a few lines above — same source of truth.
# -----------------------------------------------------------------------------
resource "kubernetes_secret_v1" "langfuse_org_keys" {
  metadata {
    name      = "langfuse-org-keys"
    namespace = var.c1_api_ns
  }
  data = {
    public_key = data.aws_secretsmanager_secret_version.langfuse_org_public_key_value.secret_string
    secret_key = data.aws_secretsmanager_secret_version.langfuse_org_secret_key_value.secret_string
  }
  type       = "Opaque"
  depends_on = [kubernetes_namespace_v1.c1_api]
}
# NOTE: if a pre-existing `c1-api/langfuse-org-keys` Secret is present in the
# cluster (e.g. leftover from the old ORD6 kubectl-apply bridging stage) the
# first apply of this resource will fail with "secrets ... already exists".
# ORD1's Jenkinsfile resolves this one-shot by running `terragrunt import`
# against this resource before `terragrunt apply` — safe to repeat, idempotent
# on already-managed resources.

# Necessary for DB credentials to be loaded into the namespace
resource "kubernetes_secret_v1" "c1_db_config" {
  metadata {
    name      = "c1-db-config"
    namespace = var.c1_api_ns
  }
  data = {
    "postgres-host"     = aws_db_instance.rds_pg_eks_db_c1_api.address,
    "postgres-port"     = aws_db_instance.rds_pg_eks_db_c1_api.port,
    "postgres-name"     = aws_db_instance.rds_pg_eks_db_c1_api.db_name,
    "postgres-user"     = var.c1_api_db_username,
    "postgres-password" = random_password.pg_db_password_c1_api.result,
  }
  depends_on = [kubernetes_namespace_v1.c1_api]
}

resource "kubernetes_config_map_v1" "c1_api_alb_config" {
  metadata {
    name      = "c1-alb-config"
    namespace = var.c1_api_ns
  }
  data = {
    SUBNETS      = join(",", var.alb_subnets)
    ACM_CERT_ARN = aws_acm_certificate.c1_api_cert.arn
    AWS_ALB_SG   = aws_security_group.exlerate_c1_api_alb_sg.id
  }
  depends_on = [kubernetes_namespace_v1.c1_api]
}


#############################################
#   Secrets mounted onto Control API pods
#############################################

# This resource manifest basically tells the namespace what secrets to fetch
resource "kubernetes_manifest" "aws_ssm_secrets_for_c1_api" {
  count = var.bootstrap_phase >= 2 ? 1 : 0
  manifest = {
    apiVersion = "secrets-store.csi.x-k8s.io/v1"
    kind       = "SecretProviderClass"
    metadata = {
      name      = var.c1_api_sec_provider_class # This is whats referenced in the SPC attribute in the Pod manifest
      namespace = var.c1_api_ns
    }
    spec = {
      provider = "aws"
      parameters = {
        objects = <<-EOT
- objectName: ${aws_secretsmanager_secret.litellm_master_key.name}
  objectType: secretsmanager
  objectAlias: "litellm-api-key"
  region: ${var.region}
- objectName: ${aws_secretsmanager_secret.langfuse_org_public_key.name}
  objectType: secretsmanager
  objectAlias: "${aws_secretsmanager_secret.langfuse_org_public_key.name}"
  region: ${var.region}
- objectName: ${aws_secretsmanager_secret.langfuse_org_secret_key.name}
  objectType: secretsmanager
  objectAlias: "${aws_secretsmanager_secret.langfuse_org_secret_key.name}"
  region: ${var.region}
EOT
      }
    }
  }
  depends_on = [module.c1_api_irsa_permissions_set,
  kubernetes_namespace_v1.c1_api]
}
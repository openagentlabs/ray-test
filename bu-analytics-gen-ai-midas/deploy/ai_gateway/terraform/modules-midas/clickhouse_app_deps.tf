# ClickHouse Permission sets and secret defintions
module "clickhouse_irsa_permissions_set" {
  source           = "./irsa_blocks"
  eks_cluster_name = var.eks_cluster_name
  application      = "clickhouse"

  eks_oidc_url      = local.eks_oidc_url # This only changes if the cluster is redeployed
  eks_namespace     = var.ch_ns
  account_id        = data.aws_caller_identity.current.account_id
  irsa_account_name = "clickhouse-irsa-account"

  policy_arns = [
    "arn:aws:iam::aws:policy/AmazonSSMReadOnlyAccess",
    "arn:aws:iam::aws:policy/AWSSecretsManagerClientReadOnlyAccess",
    "arn:aws:iam::aws:policy/AmazonS3ReadOnlyAccess",
  ]
  depends_on = [aws_eks_cluster.exlerate_eks_cluster]
}

locals {
  clickhouse_secret_vals = {
    "admin-password"    = random_password.ch_langfuse_password.result,
    "langfuse-password" = random_password.ch_langfuse_password.result,
    "ch-host"           = var.ch_host
  }
  depends_on = [kubernetes_namespace_v1.clickhouse]
}

# Secrets needed by Helm values file rather than passing them in Jenkins file
module "clickhouse_helm_chart_secrets" {
  for_each = local.clickhouse_secret_vals
  source   = "./k_secrets"

  metadataName = each.key
  secretName   = each.key
  ns           = var.ch_ns
  secretValue  = each.value
  depends_on   = [kubernetes_namespace_v1.clickhouse]
}

resource "kubernetes_secret_v1" "langfuse_clickhouse_credentials_ch" {
  metadata {
    name      = "clickhouse-credentials-${var.environment}"
    namespace = var.ch_ns

    # Helm ownership labels note if uninstalling the chart this secret needs to be reapplied
    labels = {
      "app.kubernetes.io/managed-by" = "Helm"
    }
    # Helm ownership annotations
    annotations = {
      "meta.helm.sh/release-name"      = var.ch_ns
      "meta.helm.sh/release-namespace" = var.ch_ns
    }
  }

  data = {
    password = random_password.ch_langfuse_password.result
    user     = "langfuse"
  }

  type       = "Opaque"
  depends_on = [kubernetes_namespace_v1.clickhouse]
}
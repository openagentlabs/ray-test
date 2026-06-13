# -----------------------------------------------------------------------------
# Kubernetes provider (EKS exec auth) — used when terraform_sync_app_secret_to_kubernetes
# is true to apply midas-app-secret from Secrets Manager (see kubernetes-midas-app-secret.tf).
# Apply host must reach the private EKS API; principal must match eks_ci_automation_principal_arn
# for aws eks get-token during plan/apply.
# -----------------------------------------------------------------------------

provider "kubernetes" {
  host                   = module.eks.eks_cluster_endpoint
  cluster_ca_certificate = base64decode(module.eks.eks_cluster_certificate_authority_data)

  exec {
    api_version = "client.authentication.k8s.io/v1beta1"
    command     = "aws"
    args = [
      "eks",
      "get-token",
      "--cluster-name", module.eks.eks_cluster_name,
      "--region", var.aws_region,
    ]
  }
}

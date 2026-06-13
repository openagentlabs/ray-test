resource "kubernetes_namespace" "workloads" {
  provider = kubernetes.eks

  metadata {
    name = local.namespace
    labels = {
      "app.kubernetes.io/managed-by" = "terraform"
      solution                       = var.solution.name
    }
  }
}

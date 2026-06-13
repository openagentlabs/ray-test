resource "kubernetes_namespace" "kuberay" {
  provider = kubernetes.eks

  metadata {
    name = var.namespace
    labels = {
      "app.kubernetes.io/managed-by" = "terraform"
      "app.kubernetes.io/name"       = "kuberay"
      solution                       = var.solution.name
    }
  }
}

resource "helm_release" "kuberay_operator" {
  provider = helm.eks

  name             = "kuberay-operator"
  repository       = "https://ray-project.github.io/kuberay-helm/"
  chart            = "kuberay-operator"
  version          = var.chart_version
  namespace        = kubernetes_namespace.kuberay.metadata[0].name
  create_namespace = false
  wait             = true
  timeout          = 600

  values = [
    yamlencode({
      rbacEnable             = true
      leaderElectionEnabled  = true
      crNamespacedRbacEnable = true
      singleNamespaceInstall = false

      nodeSelector = {
        (var.node_pool_label_key) = var.node_pool_label_value
      }

      resources = {
        limits = {
          cpu    = "500m"
          memory = "512Mi"
        }
        requests = {
          cpu    = "200m"
          memory = "256Mi"
        }
      }

      metrics = {
        enabled = true
      }
    }),
  ]

  depends_on = [kubernetes_namespace.kuberay]
}

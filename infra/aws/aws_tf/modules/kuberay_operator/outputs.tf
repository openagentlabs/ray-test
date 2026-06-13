output "namespace" {
  description = "Kubernetes namespace hosting KubeRay and RayCluster resources."
  value       = kubernetes_namespace.kuberay.metadata[0].name
}

output "operator_release_name" {
  description = "Helm release name for the KubeRay operator."
  value       = helm_release.kuberay_operator.name
}

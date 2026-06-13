output "head_service_name" {
  description = "Kubernetes Service name for the Ray head (dashboard port 8265)."
  value       = local.head_service_name
}

output "ingress_name" {
  description = "Ingress resource name for the Ray dashboard ALB."
  value       = kubernetes_ingress_v1.ray_dashboard.metadata[0].name
}

output "namespace" {
  description = "Kubernetes namespace hosting the RayCluster."
  value       = var.namespace
}

output "release_name" {
  description = "Helm release name for the RayCluster."
  value       = helm_release.ray_cluster.name
}

output "ray_alb_hostname" {
  description = "ALB DNS hostname for the Ray dashboard (may be empty until the controller provisions the load balancer)."
  value       = try(data.kubernetes_ingress_v1.ray_dashboard.status[0].load_balancer[0].ingress[0].hostname, "")
}

output "ray_dashboard_url" {
  description = "HTTP URL for the Ray dashboard and Jobs API (when ALB hostname is available)."
  value       = length(try(data.kubernetes_ingress_v1.ray_dashboard.status[0].load_balancer[0].ingress[0].hostname, "")) > 0 ? "http://${data.kubernetes_ingress_v1.ray_dashboard.status[0].load_balancer[0].ingress[0].hostname}/" : ""
}

output "ray_metrics_url" {
  description = "HTTP URL for Ray head Prometheus metrics (when ALB hostname is available)."
  value       = length(try(data.kubernetes_ingress_v1.ray_dashboard.status[0].load_balancer[0].ingress[0].hostname, "")) > 0 ? "http://${data.kubernetes_ingress_v1.ray_dashboard.status[0].load_balancer[0].ingress[0].hostname}/metrics" : ""
}

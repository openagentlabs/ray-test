output "cluster_name" {
  description = "EKS cluster name (from workloads_infra)."
  value       = var.cluster_name
}

output "ecr_repository_urls" {
  description = "ECR repository URLs keyed by workload."
  value       = { for k, m in module.ecr : k => m.repository_url }
}

output "k8s_namespace" {
  description = "Kubernetes namespace for ARB workloads."
  value       = var.namespace
}

output "k8s_service_dns_names" {
  description = "In-cluster DNS names for each workload (ClusterIP gRPC/HTTP)."
  value = {
    for key, cfg in local.enabled_workloads :
    key => "${cfg.k8s_service_name}.${var.namespace}.svc.cluster.local"
  }
}

output "shared_workload_role_arn" {
  description = "IRSA role ARN for workloads without a dedicated IAM role."
  value       = aws_iam_role.shared_workload.arn
}

output "workload_deploy_specs" {
  description = "Helm/kubectl deploy metadata per enabled workload."
  value = {
    for key, cfg in local.enabled_workloads :
    key => {
      container_port       = cfg.container_port
      cpu                  = cfg.cpu
      memory               = cfg.memory
      image                = "${module.ecr[key].repository_url}:${local.workload_image_tags[key]}"
      k8s_service_name     = cfg.k8s_service_name
      service_account_name = cfg.service_account_name
      task_role_arn        = coalesce(cfg.task_role_arn, aws_iam_role.shared_workload.arn)
      expose_load_balancer = cfg.expose_load_balancer
      environment = merge(
        cfg.environment,
        lookup(var.workload_extra_environment, key, {}),
      )
    }
  }
}

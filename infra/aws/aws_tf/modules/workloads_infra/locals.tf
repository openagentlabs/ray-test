locals {
  solution_slug = replace(replace(replace(lower(replace(var.solution.name, "_", "-")), "--", "-"), "--", "-"), "--", "-")

  cluster_name = length(trimspace(var.cluster_name)) > 0 ? var.cluster_name : local.solution_slug
  # Stable product namespace (ray-test); matches cluster name and PRJ_SLUG.
  namespace = length(trimspace(var.namespace)) > 0 ? var.namespace : local.solution_slug

  ray_compute_enabled = var.kuberay_enabled

  # Workloads namespace shares PVCs with Ray when FSx Lustre is enabled.
  lustre_mount_namespaces = compact([
    var.kuberay_enabled ? var.kuberay_namespace : "",
    local.namespace,
  ])

  s3_mount_namespaces = compact([
    var.kuberay_enabled ? var.kuberay_namespace : "",
    local.namespace,
  ])
}

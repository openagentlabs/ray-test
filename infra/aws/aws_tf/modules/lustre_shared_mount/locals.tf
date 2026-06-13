locals {
  # Consistent volume and mount identifiers across Ray and non-Ray EC2 workloads.
  volume_name = "shared-lustre"
  mount_path  = "/mnt/lustre"

  service_account_name = "fsx-csi-controller-sa"
  name_prefix          = replace(replace(replace(lower(replace("${var.solution.name}-${var.solution.deployment_key}-fsx-csi", "_", "-")), "--", "-"), "--", "-"), "--", "-")

  mount_namespaces = toset(var.mount_namespaces)
}

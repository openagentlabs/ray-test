locals {
  # Consistent volume and mount identifiers across Ray and non-Ray EC2 workloads.
  volume_name = "shared-lustre"
  mount_path  = "/mnt/lustre"

  service_account_name = "fsx-csi-controller-sa"
  _name_prefix_raw     = lower(replace("${var.solution.name}-${var.solution.deployment_key}-fsx-csi", "_", "-"))
  name_prefix          = can(regex("--", var.solution.deployment_key)) ? local._name_prefix_raw : replace(replace(replace(local._name_prefix_raw, "--", "-"), "--", "-"), "--", "-")

  mount_namespaces = toset(var.mount_namespaces)
}

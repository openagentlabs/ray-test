locals {
  # Consistent volume and mount identifiers across Ray and non-Ray EC2 workloads.
  volume_name = "shared-s3-files"
  mount_path  = "/mnt/s3-files"

  service_account_name = "s3-csi-driver-sa"
  _name_prefix_raw     = lower(replace("${var.solution.name}-${var.solution.deployment_key}-s3-csi", "_", "-"))
  name_prefix          = can(regex("--", var.solution.deployment_key)) ? local._name_prefix_raw : replace(replace(replace(local._name_prefix_raw, "--", "-"), "--", "-"), "--", "-")

  mount_namespaces = toset(var.mount_namespaces)

  normalized_bucket_key_prefix = (
    endswith(trimspace(var.bucket_key_prefix), "/")
    ? trimspace(var.bucket_key_prefix)
    : "${trimspace(var.bucket_key_prefix)}/"
  )

  # Mountpoint CSI mountOptions use space-separated flags (see awslabs/mountpoint-s3-csi-driver examples).
  mount_options = [
    "allow-other",
    "allow-delete",
    "allow-overwrite",
    "region ${var.solution.region}",
    "prefix ${local.normalized_bucket_key_prefix}",
  ]

  s3_object_resource_arn = "${var.bucket_arn}/${trim(local.normalized_bucket_key_prefix, "/")}/*"

  list_bucket_prefixes = distinct([
    local.normalized_bucket_key_prefix,
    trimsuffix(local.normalized_bucket_key_prefix, "/"),
    "${trimsuffix(local.normalized_bucket_key_prefix, "/")}/*",
  ])
}

check "s3_shared_mount_bucket_inputs" {
  assert {
    condition = (
      length(trimspace(var.bucket_arn)) > 0 &&
      length(trimspace(var.bucket_name)) > 0
    )
    error_message = "s3_shared_mount requires non-empty bucket_arn and bucket_name from module.s3_shared_files."
  }
}

check "s3_shared_mount_namespaces" {
  assert {
    condition     = length(var.mount_namespaces) > 0
    error_message = "s3_shared_mount mount_namespaces must include at least one namespace (kuberay and workloads)."
  }
}

check "s3_shared_mount_key_prefix" {
  assert {
    condition     = length(trimspace(var.bucket_key_prefix)) > 0
    error_message = "bucket_key_prefix must be non-empty (default shared/)."
  }
}

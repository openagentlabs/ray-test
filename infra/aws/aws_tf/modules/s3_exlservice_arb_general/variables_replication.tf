###############################################################################
# infra/tf_lib/s3 — replication input
###############################################################################

variable "replication" {
  description = <<-EOT
    Single-destination replication configuration. null disables it.

    Fields:
      destination_bucket_arn    — target bucket ARN (same or different region).
      iam_role_arn              — pre-created IAM role with replication perms.
      prefix                    — optional source-side key prefix filter.
      destination_storage_class — optional override for replicated objects.
      delete_marker_replication — copy delete markers (default false).
      destination_kms_key_arn   — required only if destination uses SSE-KMS.

    Validation requires `versioning_enabled = true` because S3 replication
    only works on versioned source buckets.
  EOT
  type = object({
    destination_bucket_arn    = string
    iam_role_arn              = string
    prefix                    = optional(string, null)
    destination_storage_class = optional(string, null)
    delete_marker_replication = optional(bool, false)
    destination_kms_key_arn   = optional(string, null)
  })
  default = null
}

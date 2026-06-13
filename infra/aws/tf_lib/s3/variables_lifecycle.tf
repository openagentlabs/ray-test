###############################################################################
# infra/tf_lib/s3 — lifecycle-related inputs
# Variables in this file: alphabetical order.
###############################################################################

variable "abort_incomplete_multipart_upload_days" {
  description = <<-EOT
    If non-null, the module emits a dedicated lifecycle rule that aborts any
    multipart upload not completed within this many days.

    Orphan multipart uploads silently accrue storage cost because their parts
    are billed but invisible to ListObjects. AWS recommendation: 7.

    Set to null to disable this convenience rule (you can still express the
    same behaviour inside `lifecycle_rules` if you prefer).
  EOT
  type        = number
  default     = null

  validation {
    condition     = var.abort_incomplete_multipart_upload_days == null || try(var.abort_incomplete_multipart_upload_days > 0, false)
    error_message = "abort_incomplete_multipart_upload_days must be null or a positive integer."
  }
}

variable "lifecycle_rules" {
  description = <<-EOT
    Full-schema passthrough list for `aws_s3_bucket_lifecycle_configuration`.
    Each rule mirrors the AWS provider schema 1:1.

    Use this to:
      - transition objects between storage classes over time
      - expire current/noncurrent versions
      - delete expired delete-markers
      - abort incomplete multipart uploads (or use the dedicated
        `abort_incomplete_multipart_upload_days` input instead)

    Example:
      [
        {
          id     = "logs-cold-archive"
          status = "Enabled"
          filter = { prefix = "logs/" }
          transitions = [
            { days = 30,  storage_class = "STANDARD_IA" },
            { days = 90,  storage_class = "GLACIER" },
            { days = 365, storage_class = "DEEP_ARCHIVE" },
          ]
          expiration                    = { days = 730 }
          noncurrent_version_expiration = { noncurrent_days = 90 }
        },
      ]
  EOT
  type = list(object({
    id     = string
    status = optional(string, "Enabled")

    filter = optional(object({
      prefix                   = optional(string)
      object_size_greater_than = optional(number)
      object_size_less_than    = optional(number)
      tag = optional(object({
        key   = string
        value = string
      }))
      and = optional(object({
        prefix                   = optional(string)
        object_size_greater_than = optional(number)
        object_size_less_than    = optional(number)
        tags                     = optional(map(string))
      }))
    }))

    transitions = optional(list(object({
      days          = optional(number)
      date          = optional(string)
      storage_class = string
    })), [])

    noncurrent_version_transitions = optional(list(object({
      noncurrent_days           = number
      newer_noncurrent_versions = optional(number)
      storage_class             = string
    })), [])

    expiration = optional(object({
      days                         = optional(number)
      date                         = optional(string)
      expired_object_delete_marker = optional(bool)
    }))

    noncurrent_version_expiration = optional(object({
      noncurrent_days           = number
      newer_noncurrent_versions = optional(number)
    }))

    abort_incomplete_multipart_upload = optional(object({
      days_after_initiation = number
    }))
  }))
  default  = []
  nullable = false
}

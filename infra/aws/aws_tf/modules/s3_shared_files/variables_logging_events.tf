###############################################################################
# infra/tf_lib/s3_shared_files — access logging, EventBridge, inventory
# Variables in this file: alphabetical order.
###############################################################################

variable "access_logging" {
  description = <<-EOT
    Server access logging configuration. null disables it.

    When set, every request to this bucket is logged to `target_bucket` under
    `target_prefix`. `target_bucket` MUST be a different bucket (logging to
    self creates an infinite loop and is rejected by validation).

    For higher-fidelity audit (IAM principal, request ID, full request body),
    consider CloudTrail S3 data events at the account level instead.
  EOT
  type = object({
    target_bucket = string
    target_prefix = optional(string, "")
  })
  default = null
}

variable "eventbridge_enabled" {
  description = <<-EOT
    When true, S3 object events (create, delete, restore, etc.) are forwarded
    to the default EventBridge bus. Rules and downstream consumers are owned
    by the caller; this module only opens the firehose.
  EOT
  type        = bool
  default     = false
  nullable    = false
}

variable "inventory" {
  description = <<-EOT
    S3 Inventory configuration. null disables it.

    When set, the bucket emits a periodic flat-file manifest of its contents
    to `destination_bucket_arn`. Useful for large-scale Batch Operations,
    regulatory reporting, and replication audits.

    Fields:
      id                       — name of the inventory configuration.
      destination_bucket_arn   — bucket receiving the manifest files.
      destination_prefix       — key prefix in destination bucket (optional).
      destination_format       — "CSV" | "ORC" | "Parquet".
      schedule_frequency       — "Daily" | "Weekly".
      included_object_versions — "Current" | "All".
      optional_fields          — list of optional fields (e.g. Size, ETag).
      filter_prefix            — only inventory objects under this prefix.
  EOT
  type = object({
    id                       = string
    destination_bucket_arn   = string
    destination_prefix       = optional(string, "")
    destination_format       = optional(string, "Parquet")
    schedule_frequency       = optional(string, "Daily")
    included_object_versions = optional(string, "Current")
    optional_fields          = optional(list(string), [])
    filter_prefix            = optional(string, null)
  })
  default = null

  validation {
    condition     = var.inventory == null || contains(["CSV", "ORC", "Parquet"], try(var.inventory.destination_format, "Parquet"))
    error_message = "inventory.destination_format must be CSV, ORC, or Parquet."
  }

  validation {
    condition     = var.inventory == null || contains(["Daily", "Weekly"], try(var.inventory.schedule_frequency, "Daily"))
    error_message = "inventory.schedule_frequency must be Daily or Weekly."
  }

  validation {
    condition     = var.inventory == null || contains(["Current", "All"], try(var.inventory.included_object_versions, "Current"))
    error_message = "inventory.included_object_versions must be Current or All."
  }
}

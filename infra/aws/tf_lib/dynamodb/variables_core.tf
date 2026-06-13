###############################################################################
# infra/tf_lib/dynamodb — core inputs
# Variables in this file: alphabetical order.
#
# Contract: boolean feature flags default false; use PAY_PER_REQUEST unless
# you explicitly choose PROVISIONED and set capacities.
###############################################################################

variable "additional_tags" {
  description = <<-EOT
    Extra tags merged on top of the root provider's `default_tags`.
  EOT
  type        = map(string)
  default     = {}
  nullable    = false
}

variable "billing_mode" {
  description = <<-EOT
    `PAY_PER_REQUEST` (default) for on-demand capacity, or `PROVISIONED` with
    `read_capacity` / `write_capacity` set to positive integers.
  EOT
  type        = string
  default     = "PAY_PER_REQUEST"
  nullable    = false

  validation {
    condition     = contains(["PAY_PER_REQUEST", "PROVISIONED"], var.billing_mode)
    error_message = "billing_mode must be PAY_PER_REQUEST or PROVISIONED."
  }
}

variable "deletion_protection_enabled" {
  description = <<-EOT
    When true, AWS rejects DeleteTable until protection is turned off. Default
    false for dev/sandbox tables; set true for production tables you must not
    drop accidentally.
  EOT
  type        = bool
  default     = false
  nullable    = false
}

variable "point_in_time_recovery_enabled" {
  description = <<-EOT
    When true, enables continuous backups / point-in-time recovery (extra
    cost). Recommended for production data; default off for minimal tables.
  EOT
  type        = bool
  default     = false
  nullable    = false
}

variable "purpose" {
  description = <<-EOT
    Short purpose suffix for the table name:

        <solution.name>-<purpose>-<solution.account_id>

    Lower snake or kebab; underscores normalized to hyphens in `local.table_name`.
  EOT
  type        = string
  nullable    = false

  validation {
    condition     = can(regex("^[a-z][a-z0-9_-]*[a-z0-9]$", var.purpose))
    error_message = "purpose must be lower_snake or lower_kebab, start with a letter, end alphanumeric."
  }
}

variable "read_capacity" {
  description = <<-EOT
    Provisioned read capacity units. Required when `billing_mode = PROVISIONED`;
    ignored for `PAY_PER_REQUEST` (leave null).
  EOT
  type        = number
  default     = null
}

variable "solution" {
  description = <<-EOT
    Solution-wide metadata from the root module (same contract as S3 tf_lib).

    Required keys: name, description, version, date, account_id, region.
  EOT
  type = object({
    name        = string
    description = string
    version     = string
    date        = string
    account_id             = string
    region                 = string
    deployment_environment = string
    deployment_index       = string
    deployment_instance    = string
    deployment_key         = string
    deployed_at            = string
    deployed_by            = string
    expires_at             = string
    cost_code              = string
    department             = string
  })
  nullable = false
}

variable "stream_enabled" {
  description = <<-EOT
    When true, enables DynamoDB Streams on this table. Requires
    `stream_view_type` to be set (see checks.tf).
  EOT
  type        = bool
  default     = false
  nullable    = false
}

variable "stream_view_type" {
  description = <<-EOT
    Stream record shape: KEYS_ONLY, NEW_IMAGE, OLD_IMAGE, or NEW_AND_OLD_IMAGES.
    Must be set when `stream_enabled` is true; leave null when streams are off.
  EOT
  type        = string
  default     = null
}

variable "table_class" {
  description = <<-EOT
    STANDARD (default) or STANDARD_INFREQUENT_ACCESS for storage-optimized
    infrequent access workloads (see AWS pricing docs).
  EOT
  type        = string
  default     = "STANDARD"
  nullable    = false

  validation {
    condition     = contains(["STANDARD", "STANDARD_INFREQUENT_ACCESS"], var.table_class)
    error_message = "table_class must be STANDARD or STANDARD_INFREQUENT_ACCESS."
  }
}

variable "ttl_attribute_name" {
  description = <<-EOT
    Attribute name used for TTL expiry (Unix epoch time, number type). Required
    when `ttl_enabled` is true; must be null when TTL is off.
  EOT
  type        = string
  default     = null
}

variable "ttl_enabled" {
  description = <<-EOT
    When true, enables TTL on the table using `ttl_attribute_name`.
  EOT
  type        = bool
  default     = false
  nullable    = false
}

variable "write_capacity" {
  description = <<-EOT
    Provisioned write capacity units. Required when `billing_mode = PROVISIONED`;
    ignored for `PAY_PER_REQUEST` (leave null).
  EOT
  type        = number
  default     = null
}

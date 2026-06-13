###############################################################################
# infra/tf_lib/s3 — versioning, MFA delete, object lock
# Variables in this file: alphabetical order.
###############################################################################

variable "mfa_delete_enabled" {
  description = <<-EOT
    When true, MFA Delete is requested on the bucket's versioning config.

    IMPORTANT: AWS only allows the bucket-owning account's ROOT user with MFA
    to actually flip MFA Delete on. IAM users, roles, and (therefore) typical
    CI credentials CANNOT apply this. After `terraform apply`, a human must
    run, as root, a one-time:

        aws s3api put-bucket-versioning \
          --bucket  <name> \
          --versioning-configuration Status=Enabled,MFADelete=Enabled \
          --mfa     "<mfa-serial> <mfa-code>"

    Requires `versioning_enabled = true` (see checks.tf).
  EOT
  type        = bool
  default     = false
  nullable    = false
}

variable "object_lock_default_retention" {
  description = <<-EOT
    Default retention applied to every new object when Object Lock is on.

      mode = "GOVERNANCE" — admins with s3:BypassGovernanceRetention can override.
      mode = "COMPLIANCE" — nobody (incl. root) can override or shorten.
      days                — retention duration in days from object upload.

    null means no default retention — callers must set retention per object.
  EOT
  type = object({
    mode = string
    days = number
  })
  default = null

  validation {
    condition     = var.object_lock_default_retention == null || contains(["GOVERNANCE", "COMPLIANCE"], try(var.object_lock_default_retention.mode, ""))
    error_message = "object_lock_default_retention.mode must be GOVERNANCE or COMPLIANCE."
  }

  validation {
    condition     = var.object_lock_default_retention == null || try(var.object_lock_default_retention.days > 0, false)
    error_message = "object_lock_default_retention.days must be a positive integer."
  }
}

variable "object_lock_enabled" {
  description = <<-EOT
    When true, Object Lock (WORM) is enabled at bucket creation.

    HARD CONSTRAINT: Object Lock can ONLY be enabled at creation time. You
    cannot retrofit it onto an existing bucket without recreating it.

    Requires `versioning_enabled = true` (see checks.tf).
  EOT
  type        = bool
  default     = false
  nullable    = false
}

variable "versioning_enabled" {
  description = <<-EOT
    When true, the bucket's `aws_s3_bucket_versioning` resource is set to
    Enabled. Required for Object Lock, MFA Delete, and Replication
    (cross-variable validation enforces these).

    Pair with a `lifecycle_rules` entry that expires noncurrent versions to
    avoid unbounded storage growth.
  EOT
  type        = bool
  default     = false
  nullable    = false
}

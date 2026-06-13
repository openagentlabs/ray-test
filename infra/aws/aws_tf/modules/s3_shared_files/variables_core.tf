###############################################################################
# infra/tf_lib/s3_shared_files — core inputs (identity, tags, defaults)
# Variables in this file: alphabetical order.
#
# Privacy contract: every boolean toggle in this module defaults to `false`.
# Leaving optional feature objects at `null` and lists empty yields a private
# bucket (blocked public ACLs/policies, TLS-only policy, no website). See
# `locals.tf` header for the full default matrix.
###############################################################################

variable "additional_tags" {
  description = <<-EOT
    Extra tags merged on top of the root provider's `default_tags`.
    Use for bucket-specific labels (e.g. DataClassification, Purpose) that do
    not belong on every resource in the stack.
  EOT
  type        = map(string)
  default     = {}
  nullable    = false
}

variable "default_storage_class" {
  description = <<-EOT
    Documented default storage class for objects in this bucket. The module
    does NOT enforce this per-object (S3 storage class is set on PUT or via
    lifecycle rules); it is exposed as an output so callers know the intent.

    Valid values and when to use them:

      STANDARD            — hot data, frequently accessed. Default.
      INTELLIGENT_TIERING — unknown/changing access patterns. AWS auto-tiers.
      STANDARD_IA         — infrequent access, instant retrieval (30-day min).
      ONEZONE_IA          — re-creatable data, single-AZ (cheaper than IA).
      GLACIER_IR          — archive with millisecond retrieval (90-day min).
      GLACIER             — archive, minutes-hours retrieval (90-day min).
      DEEP_ARCHIVE        — cold archive, hours-days retrieval (180-day min).
  EOT
  type        = string
  default     = "STANDARD"
  nullable    = false

  validation {
    condition = contains([
      "STANDARD",
      "INTELLIGENT_TIERING",
      "STANDARD_IA",
      "ONEZONE_IA",
      "GLACIER_IR",
      "GLACIER",
      "DEEP_ARCHIVE",
    ], var.default_storage_class)
    error_message = "default_storage_class must be one of STANDARD, INTELLIGENT_TIERING, STANDARD_IA, ONEZONE_IA, GLACIER_IR, GLACIER, DEEP_ARCHIVE."
  }
}

variable "force_destroy" {
  description = <<-EOT
    When true, `terraform destroy` will delete this bucket even if it still
    contains objects. Safe for dev/sandbox/CI fixtures; DANGEROUS for any
    bucket holding real data. Default is false, which is the AWS default
    (refuse to delete non-empty buckets).
  EOT
  type        = bool
  default     = false
  nullable    = false
}

variable "public_access_enabled" {
  description = <<-EOT
    Single switch that controls all four `aws_s3_bucket_public_access_block`
    flags.

      false (default) — block_public_acls, block_public_policy,
                        ignore_public_acls, restrict_public_buckets ALL true.
                        Bucket is fully private; public ACLs/policies are
                        ignored and rejected.

      true            — the four flags flip to false, allowing the bucket
                        policy and/or ACLs to grant public access. Required
                        when `website != null` (validation).

    Almost every bucket in this repo should stay at false.
  EOT
  type        = bool
  default     = false
  nullable    = false
}

variable "purpose" {
  description = <<-EOT
    Short purpose suffix appended to the bucket name. Combined with
    `solution.name` and `solution.account_id` to produce a globally unique,
    deterministic name:

        <solution.name>-<purpose>-<solution.account_id>

    Must be lower_snake_case or lower-kebab-case. Underscores are converted
    to hyphens automatically (S3 bucket names cannot contain underscores).
  EOT
  type        = string
  nullable    = false

  validation {
    condition     = can(regex("^[a-z][a-z0-9_-]*[a-z0-9]$", var.purpose))
    error_message = "purpose must be lower-snake or lower-kebab, start with a letter, end alphanumeric."
  }
}

variable "solution" {
  description = <<-EOT
    Solution-wide metadata propagated from the root module
    (see infra/aws_tf root variables.tf and locals.tf).

    Required keys:
      name        — short slug for the solution (lower_snake_case).
      description — human-readable description.
      version     — semver (MAJOR.MINOR.PATCH).
      date        — release date (YYYY-MM-DD).
      account_id  — AWS account ID this stack deploys into.
      region      — AWS region this stack deploys into.
  EOT
  type = object({
    name                   = string
    description            = string
    version                = string
    date                   = string
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

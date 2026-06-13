###############################################################################
# infra/tf_lib/s3_shared_files — optional public anonymous object access + CORS
#
# Public object ACLs remain off (BucketOwnerEnforced); access is bucket-policy
# only. Prefer tightening origins in `cors_rules` instead of "*" in production.
###############################################################################

variable "bucket_name_override" {
  description = <<-EOT
    When set, use this exact global bucket name instead of the default pattern
    `<solution.name>-<purpose>-<solution.account_id>`. Must be 3–63 characters,
    DNS-compliant, lower-case. Leave null to use the computed name (recommended
    for uniqueness).
  EOT
  type        = string
  default     = null
  nullable    = true

  validation {
    condition = (
      var.bucket_name_override == null
      ) || (
      length(var.bucket_name_override) >= 3
      && length(var.bucket_name_override) <= 63
      && can(regex("^[a-z0-9][a-z0-9.-]*[a-z0-9]$", var.bucket_name_override))
      && !can(regex("\\.\\.|\\.\\-|\\-\\.", var.bucket_name_override))
    )
    error_message = "bucket_name_override must be null or a valid S3 bucket name (3–63 chars, lowercase letters, digits, dots, hyphens; no adjacent period-hyphen patterns)."
  }
}

variable "cors_rules" {
  description = <<-EOT
    Optional CORS rules for browser clients (e.g. SPA uploads). Empty list
    omits `aws_s3_bucket_cors_configuration`. Prefer explicit origins over "*"
    outside sandboxes.
  EOT
  type = list(object({
    allowed_headers = optional(list(string), ["*"])
    allowed_methods = list(string)
    allowed_origins = list(string)
    expose_headers  = optional(list(string), [])
    max_age_seconds = optional(number)
  }))
  default  = []
  nullable = false
}

variable "public_anonymous_object_read" {
  description = <<-EOT
    When true, bucket policy allows `s3:GetObject` for all principals on all
    objects (`<bucket>/*`). Requires `public_access_enabled = true`.
  EOT
  type        = bool
  default     = false
  nullable    = false
}

variable "public_anonymous_object_write" {
  description = <<-EOT
    When true, bucket policy allows `s3:PutObject` for all principals on all
    objects. This is highly permissive (anyone on the internet can upload).
    Requires `public_access_enabled = true`.
  EOT
  type        = bool
  default     = false
  nullable    = false
}

###############################################################################
# infra/tf_lib/s3_shared_files — transfer acceleration and static website
# Variables in this file: alphabetical order.
###############################################################################

variable "transfer_acceleration_enabled" {
  description = <<-EOT
    When true, enables S3 Transfer Acceleration (uploads/downloads routed
    through the CloudFront edge network). Adds ~$0.04/GB to transfer cost.

    Almost never useful for internal/private buckets used by in-region
    services. Genuine fit: global users uploading large files to a single
    central bucket.
  EOT
  type        = bool
  default     = false
  nullable    = false
}

variable "website" {
  description = <<-EOT
    Static website hosting configuration. null disables it.

    Set exactly ONE of:
      - { index_document, error_document } — bucket serves these documents.
      - { redirect_all_requests_to }       — bucket redirects every request.

    HARD CONSTRAINT: when non-null, `public_access_enabled` must be true.
    The module emits a Principal=* `s3:GetObject` Allow statement on top of
    the locked-in TLS-only Deny statement. For real production sites prefer
    CloudFront + Origin Access Control over an internet-facing S3 bucket.
  EOT
  type = object({
    index_document           = optional(string, null)
    error_document           = optional(string, null)
    redirect_all_requests_to = optional(string, null)
  })
  default = null

  validation {
    condition = var.website == null || (
      (var.website.redirect_all_requests_to != null) !=
      (var.website.index_document != null || var.website.error_document != null)
    )
    error_message = "website: set either redirect_all_requests_to OR index_document/error_document, not both."
  }
}

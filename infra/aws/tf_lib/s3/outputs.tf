###############################################################################
# infra/tf_lib/s3 — outputs
#
# Every output has a description so root modules and documentation stay clear.
###############################################################################

output "bucket_arn" {
  description = "ARN of the S3 bucket."
  value       = aws_s3_bucket.this.arn
}

output "bucket_domain_name" {
  description = "Legacy global endpoint host name (virtual-hosted-style). Prefer regional_domain_name for new clients."
  value       = aws_s3_bucket.this.bucket_domain_name
}

output "bucket_id" {
  description = "Same as bucket_name; Terraform id of the bucket."
  value       = aws_s3_bucket.this.id
}

output "bucket_name" {
  description = "Globally unique bucket name (either `bucket_name_override` or `<solution.name>-<purpose>-<account_id>` with underscores normalized to hyphens)."
  value       = aws_s3_bucket.this.bucket
}

output "bucket_regional_domain_name" {
  description = "Regional virtual-hosted-style endpoint for the bucket (recommended for in-region access)."
  value       = aws_s3_bucket.this.bucket_regional_domain_name
}

output "customer_managed_key_enabled" {
  description = "Whether SSE-KMS with a customer-managed key is enabled (otherwise SSE-S3 / AES256)."
  value       = var.customer_managed_key_enabled
}

output "default_storage_class" {
  description = "Intended default storage class for objects (documented intent; set per-object on PUT or via lifecycle)."
  value       = var.default_storage_class
}

output "encryption_sse_algorithm" {
  description = "SSE algorithm callers should use on PutObject: AES256 (SSE-S3) or aws:kms (SSE-KMS)."
  value       = local.encryption_algorithm
}

output "hosted_zone_id" {
  description = "Route 53 hosted zone ID for S3 website or alias records (same for all buckets in a region)."
  value       = aws_s3_bucket.this.hosted_zone_id
}

output "kms_key_arn" {
  description = "KMS key ARN when customer_managed_key_enabled is true; otherwise null."
  value       = var.customer_managed_key_enabled ? var.kms_key_arn : null
}

output "object_url_https_prefix" {
  description = <<-EOT
    HTTPS URL prefix for path-style object access in this bucket's region
    (`https://s3.<region>.amazonaws.com/<bucket>/`). Append an object key; TLS is
    enforced by the bucket policy's DenyInsecureTransport statement.
  EOT
  value = "https://s3.${var.solution.region}.amazonaws.com/${aws_s3_bucket.this.bucket}/"
}

output "simple_private_bucket" {
  description = <<-EOT
    True when this module is using its default private posture: public access
    block remains fully restrictive (`public_access_enabled = false`) and
    static website hosting is off (`website = null`). All boolean feature
    flags default to false across the module; this output is the one-line
    summary for callers and tests.
  EOT
  value       = local.simple_private_bucket
}

output "public_access_enabled" {
  description = "Whether all four public-access-block flags are lifted (required for static website hosting)."
  value       = var.public_access_enabled
}

output "region" {
  description = "AWS region from var.solution.region (where the bucket was created)."
  value       = var.solution.region
}

output "website_endpoint" {
  description = "Website endpoint URL when website hosting is enabled; otherwise null."
  value       = try(aws_s3_bucket_website_configuration.this[0].website_endpoint, null)
}

output "website_domain" {
  description = "Website domain host when website hosting is enabled; otherwise null."
  value       = try(aws_s3_bucket_website_configuration.this[0].website_domain, null)
}

output "versioning_status" {
  description = "Versioning status when the versioning resource exists: Enabled or Suspended; null if versioning resource was not created."
  value = try(
    aws_s3_bucket_versioning.this[0].versioning_configuration[0].status,
    null,
  )
}

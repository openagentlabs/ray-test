###############################################################################
# infra/tf_lib/s3_shared_files — locals (single place for derived values used across files)
#
# Layout: one concern per .tf file (bucket, encryption, policy, lifecycle, …).
# Do not collapse the module back into a single main.tf.
#
# Default = private “simple bucket”
#   Every boolean feature flag across `variables_*.tf` defaults to `false`.
#   Optional objects (`website`, `replication`, `access_logging`, `inventory`)
#   default to `null` (off). Lists default empty (`lifecycle_rules`, tags map).
#   `default_storage_class` is the only non-boolean default (`STANDARD`); it
#   does not change privacy — it is documentation for callers and lifecycle.
#   With defaults only: public access block fully ON (blocks public ACLs and
#   public bucket policies), no static website, TLS-only bucket policy, SSE-S3,
#   object ownership BucketOwnerEnforced (no object ACL surface).
###############################################################################

locals {
  _bucket_name_raw = lower(replace(
    "${var.solution.name}-${var.solution.deployment_key}-${var.purpose}-${var.solution.account_id}",
    "_",
    "-",
  ))
  bucket_name = var.bucket_name_override != null ? var.bucket_name_override : (
    can(regex("--", var.solution.deployment_key)) ? local._bucket_name_raw : replace(replace(replace(local._bucket_name_raw, "--", "-"), "--", "-"), "--", "-")
  )

  encryption_algorithm = var.customer_managed_key_enabled ? "aws:kms" : "AES256"

  block_public_flags = var.public_access_enabled ? false : true

  emit_lifecycle = length(var.lifecycle_rules) > 0 || var.abort_incomplete_multipart_upload_days != null

  module_tags = merge(
    {
      "s3:Purpose" = var.purpose
    },
    var.additional_tags,
  )

  # True when anonymous/public-internet exposure is off: public access block
  # stays in default “closed” mode and static website is not configured.
  simple_private_bucket = !var.public_access_enabled && var.website == null
}

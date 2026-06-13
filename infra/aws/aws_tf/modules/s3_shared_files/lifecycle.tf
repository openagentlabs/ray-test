###############################################################################
# infra/tf_lib/s3_shared_files — lifecycle configuration
#
# A single `aws_s3_bucket_lifecycle_configuration` resource carries:
#   1. user-supplied rules from `var.lifecycle_rules` (full AWS schema)
#   2. an optional dedicated rule for aborting incomplete multipart uploads,
#      driven by `var.abort_incomplete_multipart_upload_days`
#
# The whole resource is only emitted when at least one of those exists.
###############################################################################

locals {
  abort_mpu_rule = var.abort_incomplete_multipart_upload_days == null ? [] : [
    {
      id                             = "abort-incomplete-multipart-uploads"
      status                         = "Enabled"
      filter                         = null
      transitions                    = []
      noncurrent_version_transitions = []
      expiration                     = null
      noncurrent_version_expiration  = null
      abort_incomplete_multipart_upload = {
        days_after_initiation = var.abort_incomplete_multipart_upload_days
      }
    },
  ]

  all_lifecycle_rules = concat(var.lifecycle_rules, local.abort_mpu_rule)
}

resource "aws_s3_bucket_lifecycle_configuration" "this" {
  count = local.emit_lifecycle ? 1 : 0

  bucket = aws_s3_bucket.this.id

  dynamic "rule" {
    for_each = local.all_lifecycle_rules
    content {
      id     = rule.value.id
      status = try(rule.value.status, "Enabled")

      # ---------------------------------------------------------------------
      # filter — always emitted (S3 requires it). An omitted user filter
      # produces an empty `filter {}` that matches every object.
      # ---------------------------------------------------------------------
      filter {
        prefix                   = try(rule.value.filter.prefix, null)
        object_size_greater_than = try(rule.value.filter.object_size_greater_than, null)
        object_size_less_than    = try(rule.value.filter.object_size_less_than, null)

        dynamic "tag" {
          for_each = try(rule.value.filter.tag, null) == null ? [] : [rule.value.filter.tag]
          content {
            key   = tag.value.key
            value = tag.value.value
          }
        }

        dynamic "and" {
          for_each = try(rule.value.filter.and, null) == null ? [] : [rule.value.filter.and]
          content {
            prefix                   = try(and.value.prefix, null)
            object_size_greater_than = try(and.value.object_size_greater_than, null)
            object_size_less_than    = try(and.value.object_size_less_than, null)
            tags                     = try(and.value.tags, null)
          }
        }
      }

      # ---------------------------------------------------------------------
      # transitions (current versions)
      # ---------------------------------------------------------------------
      dynamic "transition" {
        for_each = try(rule.value.transitions, [])
        content {
          days          = try(transition.value.days, null)
          date          = try(transition.value.date, null)
          storage_class = transition.value.storage_class
        }
      }

      # ---------------------------------------------------------------------
      # noncurrent version transitions
      # ---------------------------------------------------------------------
      dynamic "noncurrent_version_transition" {
        for_each = try(rule.value.noncurrent_version_transitions, [])
        content {
          noncurrent_days           = noncurrent_version_transition.value.noncurrent_days
          newer_noncurrent_versions = try(noncurrent_version_transition.value.newer_noncurrent_versions, null)
          storage_class             = noncurrent_version_transition.value.storage_class
        }
      }

      # ---------------------------------------------------------------------
      # expiration (current versions)
      # ---------------------------------------------------------------------
      dynamic "expiration" {
        for_each = try(rule.value.expiration, null) == null ? [] : [rule.value.expiration]
        content {
          days                         = try(expiration.value.days, null)
          date                         = try(expiration.value.date, null)
          expired_object_delete_marker = try(expiration.value.expired_object_delete_marker, null)
        }
      }

      # ---------------------------------------------------------------------
      # noncurrent version expiration
      # ---------------------------------------------------------------------
      dynamic "noncurrent_version_expiration" {
        for_each = try(rule.value.noncurrent_version_expiration, null) == null ? [] : [rule.value.noncurrent_version_expiration]
        content {
          noncurrent_days           = noncurrent_version_expiration.value.noncurrent_days
          newer_noncurrent_versions = try(noncurrent_version_expiration.value.newer_noncurrent_versions, null)
        }
      }

      # ---------------------------------------------------------------------
      # abort incomplete multipart upload
      # ---------------------------------------------------------------------
      dynamic "abort_incomplete_multipart_upload" {
        for_each = try(rule.value.abort_incomplete_multipart_upload, null) == null ? [] : [rule.value.abort_incomplete_multipart_upload]
        content {
          days_after_initiation = abort_incomplete_multipart_upload.value.days_after_initiation
        }
      }
    }
  }

  depends_on = [
    aws_s3_bucket_versioning.this,
  ]
}

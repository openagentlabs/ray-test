###############################################################################
# infra/tf_lib/s3_shared_files — replication (single destination, simple style)
#
# Emitted only when var.replication != null. Replication requires:
#   - versioning_enabled = true (enforced by variable validation)
#   - an externally-managed IAM role (var.replication.iam_role_arn) granting
#     this bucket permission to read source objects and replicate them to the
#     destination bucket
#   - if destination uses SSE-KMS: var.replication.destination_kms_key_arn
###############################################################################

resource "aws_s3_bucket_replication_configuration" "this" {
  count = var.replication == null ? 0 : 1

  bucket = aws_s3_bucket.this.id
  role   = var.replication.iam_role_arn

  rule {
    id     = "primary-replication"
    status = "Enabled"

    # Empty prefix = entire bucket (AWS replication scope). Omitting `filter`
    # is invalid in the provider schema; use prefix = "" when no prefix filter.
    filter {
      prefix = coalesce(var.replication.prefix, "")
    }

    delete_marker_replication {
      status = var.replication.delete_marker_replication ? "Enabled" : "Disabled"
    }

    destination {
      bucket        = var.replication.destination_bucket_arn
      storage_class = try(var.replication.destination_storage_class, null)

      dynamic "encryption_configuration" {
        for_each = try(var.replication.destination_kms_key_arn, null) == null ? [] : [var.replication.destination_kms_key_arn]
        content {
          replica_kms_key_id = encryption_configuration.value
        }
      }
    }

    # When the source bucket uses SSE-KMS, we must opt into replicating
    # KMS-encrypted objects.
    dynamic "source_selection_criteria" {
      for_each = var.customer_managed_key_enabled ? [1] : []
      content {
        sse_kms_encrypted_objects {
          status = "Enabled"
        }
      }
    }
  }

  depends_on = [
    aws_s3_bucket_versioning.this,
  ]
}

###############################################################################
# infra/tf_lib/s3_shared_files — server-side encryption at rest (SSE-S3 or SSE-KMS)
###############################################################################

resource "aws_s3_bucket_server_side_encryption_configuration" "this" {
  bucket = aws_s3_bucket.this.id

  rule {
    bucket_key_enabled = var.customer_managed_key_enabled

    apply_server_side_encryption_by_default {
      sse_algorithm     = local.encryption_algorithm
      kms_master_key_id = var.customer_managed_key_enabled ? var.kms_key_arn : null
    }
  }
}

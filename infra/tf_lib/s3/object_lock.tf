###############################################################################
# infra/tf_lib/s3 — object lock default retention (optional)
#
# `object_lock_enabled` is set on the bucket at creation in bucket.tf.
###############################################################################

resource "aws_s3_bucket_object_lock_configuration" "this" {
  count = var.object_lock_enabled && var.object_lock_default_retention != null ? 1 : 0

  bucket = aws_s3_bucket.this.id

  rule {
    default_retention {
      mode = var.object_lock_default_retention.mode
      days = var.object_lock_default_retention.days
    }
  }

  depends_on = [
    aws_s3_bucket_versioning.this,
  ]
}

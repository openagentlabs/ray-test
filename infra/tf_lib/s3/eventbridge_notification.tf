###############################################################################
# infra/tf_lib/s3 — EventBridge integration for S3 events (opt-in)
###############################################################################

resource "aws_s3_bucket_notification" "this" {
  count = var.eventbridge_enabled ? 1 : 0

  bucket      = aws_s3_bucket.this.id
  eventbridge = true
}

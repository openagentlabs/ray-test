###############################################################################
# infra/tf_lib/s3 — transfer acceleration (opt-in)
###############################################################################

resource "aws_s3_bucket_accelerate_configuration" "this" {
  count = var.transfer_acceleration_enabled ? 1 : 0

  bucket = aws_s3_bucket.this.id
  status = "Enabled"
}

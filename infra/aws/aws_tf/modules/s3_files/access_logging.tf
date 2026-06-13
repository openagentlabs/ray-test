###############################################################################
# infra/tf_lib/s3 — server access logging to another bucket (opt-in)
#
# checks.tf forbids logging to this module's own bucket name.
###############################################################################

resource "aws_s3_bucket_logging" "this" {
  count = var.access_logging == null ? 0 : 1

  bucket = aws_s3_bucket.this.id

  target_bucket = var.access_logging.target_bucket
  target_prefix = var.access_logging.target_prefix
}

###############################################################################
# infra/tf_lib/s3 — object ownership (ACLs disabled; no user-facing flag)
###############################################################################

resource "aws_s3_bucket_ownership_controls" "this" {
  bucket = aws_s3_bucket.this.id

  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

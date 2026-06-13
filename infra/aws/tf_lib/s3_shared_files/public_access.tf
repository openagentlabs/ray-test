###############################################################################
# infra/tf_lib/s3_shared_files — public access block (single flag drives all four settings)
###############################################################################

resource "aws_s3_bucket_public_access_block" "this" {
  bucket = aws_s3_bucket.this.id

  block_public_acls       = local.block_public_flags
  block_public_policy     = local.block_public_flags
  ignore_public_acls      = local.block_public_flags
  restrict_public_buckets = local.block_public_flags
}

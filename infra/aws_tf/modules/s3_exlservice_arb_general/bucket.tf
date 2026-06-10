###############################################################################
# infra/tf_lib/s3 — primary bucket resource only
###############################################################################

resource "aws_s3_bucket" "this" {
  bucket = local.bucket_name

  force_destroy       = var.force_destroy
  object_lock_enabled = var.object_lock_enabled

  tags = local.module_tags
}

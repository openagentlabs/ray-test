###############################################################################
# infra/tf_lib/s3 — versioning and MFA Delete request on versioning config
#
# Created when versioning, MFA delete, or object lock is requested (object lock
# requires versioning on the bucket).
###############################################################################

resource "aws_s3_bucket_versioning" "this" {
  count = var.versioning_enabled || var.mfa_delete_enabled || var.object_lock_enabled ? 1 : 0

  bucket = aws_s3_bucket.this.id

  versioning_configuration {
    status     = var.versioning_enabled || var.object_lock_enabled ? "Enabled" : "Suspended"
    mfa_delete = var.mfa_delete_enabled ? "Enabled" : "Disabled"
  }
}

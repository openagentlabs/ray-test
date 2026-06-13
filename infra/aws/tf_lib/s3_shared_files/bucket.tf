###############################################################################
# infra/tf_lib/s3_shared_files — primary bucket resource
#
# Based on hashicorp/aws aws_s3_bucket:
# https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/s3_bucket
###############################################################################

resource "aws_s3_bucket" "this" {
  bucket = local.bucket_name

  force_destroy       = var.force_destroy
  object_lock_enabled = var.object_lock_enabled

  tags = local.module_tags
}

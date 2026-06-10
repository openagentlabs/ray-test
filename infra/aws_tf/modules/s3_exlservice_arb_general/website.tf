###############################################################################
# infra/tf_lib/s3 — static website hosting (opt-in via var.website)
#
# Cross-variable checks in checks.tf require public_access_enabled when website
# is set. Website config must be exactly one of index/error or redirect.
###############################################################################

resource "aws_s3_bucket_website_configuration" "this" {
  count = var.website == null ? 0 : 1

  bucket = aws_s3_bucket.this.id

  dynamic "index_document" {
    for_each = var.website.index_document == null ? [] : [var.website.index_document]
    content {
      suffix = index_document.value
    }
  }

  dynamic "error_document" {
    for_each = var.website.error_document == null ? [] : [var.website.error_document]
    content {
      key = error_document.value
    }
  }

  dynamic "redirect_all_requests_to" {
    for_each = var.website.redirect_all_requests_to == null ? [] : [var.website.redirect_all_requests_to]
    content {
      host_name = redirect_all_requests_to.value
    }
  }

  depends_on = [
    aws_s3_bucket_public_access_block.this,
    aws_s3_bucket_policy.this,
  ]
}

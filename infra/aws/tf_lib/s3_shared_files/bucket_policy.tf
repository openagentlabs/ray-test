###############################################################################
# infra/tf_lib/s3_shared_files — bucket policy (TLS-only baseline + optional website read)
###############################################################################

data "aws_iam_policy_document" "bucket" {
  statement {
    sid    = "DenyInsecureTransport"
    effect = "Deny"

    principals {
      type        = "*"
      identifiers = ["*"]
    }

    actions = ["s3:*"]

    resources = [
      aws_s3_bucket.this.arn,
      "${aws_s3_bucket.this.arn}/*",
    ]

    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }

  dynamic "statement" {
    for_each = var.website == null ? [] : [1]
    content {
      sid    = "PublicReadGetObject"
      effect = "Allow"

      principals {
        type        = "*"
        identifiers = ["*"]
      }

      actions   = ["s3:GetObject"]
      resources = ["${aws_s3_bucket.this.arn}/*"]
    }
  }

  dynamic "statement" {
    for_each = var.public_anonymous_object_read ? [1] : []
    content {
      sid    = "PublicAnonymousReadObjects"
      effect = "Allow"

      principals {
        type        = "*"
        identifiers = ["*"]
      }

      actions   = ["s3:GetObject"]
      resources = ["${aws_s3_bucket.this.arn}/*"]
    }
  }

  dynamic "statement" {
    for_each = var.public_anonymous_object_write ? [1] : []
    content {
      sid    = "PublicAnonymousWriteObjects"
      effect = "Allow"

      principals {
        type        = "*"
        identifiers = ["*"]
      }

      actions   = ["s3:PutObject"]
      resources = ["${aws_s3_bucket.this.arn}/*"]
    }
  }
}

resource "aws_s3_bucket_policy" "this" {
  bucket = aws_s3_bucket.this.id
  policy = data.aws_iam_policy_document.bucket.json

  depends_on = [
    aws_s3_bucket_public_access_block.this,
  ]
}

# MIDAS S3 test bucket - private-by-default for corporate accounts.
# Register in deploy/ecs-app/s3.tf
#
# We do NOT enable public access. BucketOwnerEnforced disables ACL-based public reads.
# Default: no aws_s3_bucket_public_access_block - many orgs deny s3:PutBucketPublicAccessBlock
# via SCP; account-wide Block Public Access should still apply. Opt in with
# var.enable_bucket_public_access_block if your org allows that API.

locals {
  name_prefix = "midas-${var.environment}-${var.aws_region}"
}

resource "aws_s3_bucket" "test" {
  bucket_prefix = "${local.name_prefix}-test-"

  tags = {
    Name        = "${local.name_prefix}-test"
    Purpose     = "midas-terraform-deploy-test"
    Environment = var.environment
    AccountId   = var.aws_account_id
    ManagedBy   = "Terraform"
  }
}

resource "aws_s3_bucket_public_access_block" "test" {
  count = var.enable_bucket_public_access_block ? 1 : 0

  bucket = aws_s3_bucket.test.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_ownership_controls" "test" {
  bucket = aws_s3_bucket.test.id

  rule {
    object_ownership = "BucketOwnerEnforced"
  }

  depends_on = [aws_s3_bucket.test]
}

resource "aws_s3_bucket_server_side_encryption_configuration" "test" {
  bucket = aws_s3_bucket.test.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

data "aws_iam_policy_document" "bucket_private" {
  statement {
    sid    = "DenyInsecureTransport"
    effect = "Deny"
    principals {
      type        = "*"
      identifiers = ["*"]
    }
    actions   = ["s3:*"]
    resources = [aws_s3_bucket.test.arn, "${aws_s3_bucket.test.arn}/*"]
    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }

  statement {
    sid    = "DenyPublicAclGrant"
    effect = "Deny"
    principals {
      type        = "*"
      identifiers = ["*"]
    }
    actions = [
      "s3:PutBucketAcl",
      "s3:PutObjectAcl",
    ]
    resources = [aws_s3_bucket.test.arn, "${aws_s3_bucket.test.arn}/*"]
    condition {
      test     = "StringEquals"
      variable = "s3:x-amz-acl"
      values   = ["public-read", "public-read-write", "authenticated-read"]
    }
  }
}

resource "aws_s3_bucket_policy" "test" {
  bucket = aws_s3_bucket.test.id
  policy = data.aws_iam_policy_document.bucket_private.json

  depends_on = [
    aws_s3_bucket_ownership_controls.test,
    aws_s3_bucket_server_side_encryption_configuration.test,
  ]
}

# CKV2_AWS_61: lifecycle rule — abort incomplete multipart uploads after 7 days
# so the test bucket does not accumulate orphan upload parts.
resource "aws_s3_bucket_lifecycle_configuration" "test" {
  bucket = aws_s3_bucket.test.id

  rule {
    id     = "abort-incomplete-multipart-upload"
    status = "Enabled"

    filter {}

    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }

  depends_on = [aws_s3_bucket_ownership_controls.test]
}

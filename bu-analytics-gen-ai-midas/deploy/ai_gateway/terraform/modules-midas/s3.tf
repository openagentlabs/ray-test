# Config Yaml bucket LiteLLM DataPlane
resource "aws_s3_bucket" "exlerate_config_bucket" {
  bucket = "${var.eks_cluster_name}-ai-gateway-litellm-config-${var.region}"
}

resource "aws_s3_bucket_ownership_controls" "config_bucket_ownership_policies" {
  bucket = aws_s3_bucket.exlerate_config_bucket.id

  rule {
    object_ownership = "BucketOwnerPreferred"
  }
}

resource "aws_s3_bucket_versioning" "exlerate_config_backup_versioning" {
  bucket = aws_s3_bucket.exlerate_config_bucket.id
  versioning_configuration {
    status = "Enabled"
  }

  depends_on = [aws_s3_bucket.exlerate_config_bucket]
}

# CKV2_AWS_61: lifecycle rules — abort incomplete multipart uploads and expire
# non-current versions so the config bucket does not accumulate orphan blobs.
resource "aws_s3_bucket_lifecycle_configuration" "config_bucket" {
  bucket = aws_s3_bucket.exlerate_config_bucket.id

  rule {
    id     = "abort-incomplete-multipart-upload"
    status = "Enabled"

    filter {}

    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }

  rule {
    id     = "expire-noncurrent-versions"
    status = "Enabled"

    filter {}

    noncurrent_version_expiration {
      noncurrent_days = 90
    }
  }

  depends_on = [aws_s3_bucket_versioning.exlerate_config_backup_versioning]
}

resource "aws_s3_bucket_policy" "exlerate_config_https_only" {
  bucket = aws_s3_bucket.exlerate_config_bucket.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "DenyInsecureTransport"
        Effect    = "Deny"
        Principal = "*"
        Action    = "s3:*"
        Resource = [
          aws_s3_bucket.exlerate_config_bucket.arn,
          "${aws_s3_bucket.exlerate_config_bucket.arn}/*"
        ]
        Condition = {
          Bool = {
            "aws:SecureTransport" = "false"
          }
        }
      }
    ]
  })

}


# Access Logs needed by Exlerate DataPlane
resource "aws_s3_bucket" "exlerate_al_bucket" {
  bucket = "${var.eks_cluster_name}-access-log-bucket"
}

resource "aws_s3_bucket_lifecycle_configuration" "delete_stale_objs" {
  bucket = aws_s3_bucket.exlerate_al_bucket.id

  rule {
    id     = "delete-after-30-days"
    status = "Enabled"

    expiration {
      days = 30
    }
  }

  rule {
    id     = "abort-incomplete-multipart-upload"
    status = "Enabled"

    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }
}

resource "aws_s3_bucket_ownership_controls" "al_bucket_ownership" {
  bucket = aws_s3_bucket.exlerate_al_bucket.id

  rule {
    object_ownership = "BucketOwnerPreferred"
  }
}

resource "aws_s3_bucket_versioning" "exlerate_al_backup_versioning" {
  bucket = aws_s3_bucket.exlerate_al_bucket.id
  versioning_configuration {
    status = "Enabled"
  }

  depends_on = [aws_s3_bucket.exlerate_al_bucket]
}

resource "aws_s3_bucket_policy" "exlerate_al_https_only" {
  bucket = aws_s3_bucket.exlerate_al_bucket.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "DenyInsecureTransport"
        Effect    = "Deny"
        Principal = "*"
        Action    = "s3:*"
        Resource = [
          aws_s3_bucket.exlerate_al_bucket.arn,
          "${aws_s3_bucket.exlerate_al_bucket.arn}/*"
        ]
        Condition = {
          Bool = {
            "aws:SecureTransport" = "false"
          }
        }
      }
    ]
  })

}

# Exlerate Log bucket needed 
resource "aws_s3_bucket" "exlerate_log_bucket" {
  bucket = "${var.eks_cluster_name}-log-bucket"
}

resource "aws_s3_bucket_lifecycle_configuration" "delete_stale_objs_log_bucket" {
  bucket = aws_s3_bucket.exlerate_log_bucket.id

  rule {
    id     = "delete-after-30-days"
    status = "Enabled"

    expiration {
      days = 30
    }
  }

  rule {
    id     = "abort-incomplete-multipart-upload"
    status = "Enabled"

    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }
}

resource "aws_s3_bucket_ownership_controls" "log_bucket_ownership" {
  bucket = aws_s3_bucket.exlerate_log_bucket.id

  rule {
    object_ownership = "BucketOwnerPreferred"
  }
}

resource "aws_s3_bucket_versioning" "exlerate_log_backup_versioning" {
  bucket = aws_s3_bucket.exlerate_log_bucket.id
  versioning_configuration {
    status = "Enabled"
  }

  depends_on = [aws_s3_bucket.exlerate_log_bucket]
}

resource "aws_s3_bucket_policy" "exlerate_log_https_only" {
  bucket = aws_s3_bucket.exlerate_log_bucket.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "DenyInsecureTransport"
        Effect    = "Deny"
        Principal = "*"
        Action    = "s3:*"
        Resource = [
          aws_s3_bucket.exlerate_log_bucket.arn,
          "${aws_s3_bucket.exlerate_log_bucket.arn}/*"
        ]
        Condition = {
          Bool = {
            "aws:SecureTransport" = "false"
          }
        }
      }
    ]
  })

}


######################################################
# Langfuse Buckets
# Exlerate Log bucket needed 
######################################################
resource "aws_s3_bucket" "exlerate_langfuse_data_bucket" {
  bucket = "${var.eks_cluster_name}-langfuse-data-bucket"
}

resource "aws_s3_bucket_lifecycle_configuration" "delete_stale_objs_data_bucket" {
  bucket = aws_s3_bucket.exlerate_langfuse_data_bucket.id

  rule {
    id     = "delete-after-30-days"
    status = "Enabled"

    expiration {
      days = 30
    }
  }

  rule {
    id     = "abort-incomplete-multipart-upload"
    status = "Enabled"

    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }
}

resource "aws_s3_bucket_ownership_controls" "data_bucket_ownership" {
  bucket = aws_s3_bucket.exlerate_langfuse_data_bucket.id

  rule {
    object_ownership = "BucketOwnerPreferred"
  }
}

resource "aws_s3_bucket_versioning" "exlerate_data_backup_versioning" {
  bucket = aws_s3_bucket.exlerate_langfuse_data_bucket.id
  versioning_configuration {
    status = "Enabled"
  }

  depends_on = [aws_s3_bucket.exlerate_langfuse_data_bucket]
}

resource "aws_s3_bucket_policy" "exlerate_data_https_only" {
  bucket = aws_s3_bucket.exlerate_langfuse_data_bucket.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "DenyInsecureTransport"
        Effect    = "Deny"
        Principal = "*"
        Action    = "s3:*"
        Resource = [
          aws_s3_bucket.exlerate_langfuse_data_bucket.arn,
          "${aws_s3_bucket.exlerate_langfuse_data_bucket.arn}/*"
        ]
        Condition = {
          Bool = {
            "aws:SecureTransport" = "false"
          }
        }
      }
    ]
  })

}


resource "aws_s3_bucket" "exlerate_langfuse_media_bucket" {
  bucket = "${var.eks_cluster_name}-langfuse-media-bucket"
}

resource "aws_s3_bucket_lifecycle_configuration" "delete_stale_objs_media_bucket" {
  bucket = aws_s3_bucket.exlerate_langfuse_media_bucket.id

  rule {
    id     = "delete-after-30-days"
    status = "Enabled"

    expiration {
      days = 30
    }
  }

  rule {
    id     = "abort-incomplete-multipart-upload"
    status = "Enabled"

    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }
}

resource "aws_s3_bucket_ownership_controls" "media_bucket_ownership" {
  bucket = aws_s3_bucket.exlerate_langfuse_media_bucket.id

  rule {
    object_ownership = "BucketOwnerPreferred"
  }
}

resource "aws_s3_bucket_versioning" "exlerate_media_backup_versioning" {
  bucket = aws_s3_bucket.exlerate_langfuse_media_bucket.id
  versioning_configuration {
    status = "Enabled"
  }

  depends_on = [aws_s3_bucket.exlerate_langfuse_media_bucket]
}

resource "aws_s3_bucket_policy" "exlerate_media_https_only" {
  bucket = aws_s3_bucket.exlerate_langfuse_media_bucket.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "DenyInsecureTransport"
        Effect    = "Deny"
        Principal = "*"
        Action    = "s3:*"
        Resource = [
          aws_s3_bucket.exlerate_langfuse_media_bucket.arn,
          "${aws_s3_bucket.exlerate_langfuse_media_bucket.arn}/*"
        ]
        Condition = {
          Bool = {
            "aws:SecureTransport" = "false"
          }
        }
      }
    ]
  })

}
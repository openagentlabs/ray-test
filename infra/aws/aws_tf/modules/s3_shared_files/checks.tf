###############################################################################
# infra/tf_lib/s3_shared_files — cross-variable checks (Terraform 1.5+)
#
# Replaces hidden `_assert_*` input variables so callers never see dummy inputs.
###############################################################################

check "customer_managed_key_requires_kms_arn" {
  assert {
    condition = (
      !var.customer_managed_key_enabled
      ) || (
      var.kms_key_arn != null && var.kms_key_arn != ""
    )
    error_message = "customer_managed_key_enabled = true requires kms_key_arn to be set to a valid KMS key ARN."
  }
}

check "mfa_delete_requires_versioning" {
  assert {
    condition     = !var.mfa_delete_enabled || var.versioning_enabled
    error_message = "mfa_delete_enabled = true requires versioning_enabled = true."
  }
}

check "object_lock_requires_versioning" {
  assert {
    condition     = !var.object_lock_enabled || var.versioning_enabled
    error_message = "object_lock_enabled = true requires versioning_enabled = true."
  }
}

check "replication_requires_versioning" {
  assert {
    condition     = var.replication == null || var.versioning_enabled
    error_message = "replication is set but versioning_enabled is false; S3 replication requires versioning on the source bucket."
  }
}

check "website_requires_public_access" {
  assert {
    condition     = var.website == null || var.public_access_enabled
    error_message = "website is set but public_access_enabled is false; static website hosting requires public read access."
  }
}

check "public_anonymous_objects_require_public_access" {
  assert {
    condition = (
      (!var.public_anonymous_object_read && !var.public_anonymous_object_write)
      ) || (
      var.public_access_enabled
    )
    error_message = "public_anonymous_object_read/write requires public_access_enabled = true (public access block must allow a public bucket policy)."
  }
}

check "access_logging_target_not_self" {
  assert {
    condition = (
      var.access_logging == null
      ) || (
      var.access_logging.target_bucket != local.bucket_name
    )
    error_message = "access_logging.target_bucket must not be this module's bucket name (avoids an infinite logging loop)."
  }
}

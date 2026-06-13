###############################################################################
# infra/tf_lib/s3 — encryption inputs
# Variables in this file: alphabetical order.
###############################################################################

variable "customer_managed_key_enabled" {
  description = <<-EOT
    Encryption-at-rest selector.

      false (default) — bucket uses SSE-S3 with the AWS-managed key (AES256).
                        No KMS surface, no KMS request costs.
      true            — bucket uses SSE-KMS with the customer-managed key
                        identified by `kms_key_arn`, and S3 Bucket Key is
                        enabled to keep KMS request costs low.

    When true, `kms_key_arn` MUST be set (see checks.tf).
  EOT
  type        = bool
  default     = false
  nullable    = false
}

variable "kms_key_arn" {
  description = <<-EOT
    ARN of the customer-managed KMS key used for SSE-KMS at rest.
    Required when `customer_managed_key_enabled = true`; ignored otherwise.
    When `customer_managed_key_enabled` is false (the default), leave null.

    The key MUST live in the same region as the bucket and grant this
    account's principals `kms:Encrypt`, `kms:Decrypt`, `kms:GenerateDataKey*`,
    and `kms:DescribeKey` on it. The module enables S3 Bucket Key to amortise
    KMS request cost.
  EOT
  type        = string
  default     = null
}

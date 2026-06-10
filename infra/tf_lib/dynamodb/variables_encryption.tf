###############################################################################
# infra/tf_lib/dynamodb — encryption inputs
# Variables in this file: alphabetical order.
###############################################################################

variable "customer_managed_encryption_enabled" {
  description = <<-EOT
    When false (default), DynamoDB uses an AWS-owned key for encryption at rest.
    When true, set `kms_key_arn` to a CMK in this account/region (see checks.tf).
  EOT
  type        = bool
  default     = false
  nullable    = false
}

variable "kms_key_arn" {
  description = <<-EOT
    KMS key ARN for SSE-KMS on the table. Required when
    `customer_managed_encryption_enabled` is true; otherwise null.
  EOT
  type        = string
  default     = null
}

variable "environment" {
  description = "Deployment environment (e.g. dev, uat, prod). Used in the log group name: /midas/<environment>/backend"
  type        = string
}

variable "retention_in_days" {
  description = "CloudWatch log retention in days."
  type        = number
  default     = 30
}

variable "kms_key_arn" {
  description = "Optional KMS CMK ARN for server-side encryption of the log group. Leave empty to use the AWS-managed default."
  type        = string
  default     = ""
}

variable "tags" {
  description = "Additional tags to merge onto all resources."
  type        = map(string)
  default     = {}
}

variable "solution" {
  description = "Solution bundle (name, account_id, region) used for log group paths and tags."
  type = object({
    name       = string
    account_id = string
    region     = string
  })
  nullable = false
}

variable "retention_in_days" {
  description = "CloudWatch Logs retention for application log groups."
  type        = number
  nullable    = false
  default     = 30
}

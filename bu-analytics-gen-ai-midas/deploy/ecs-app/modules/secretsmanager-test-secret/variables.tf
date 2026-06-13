variable "aws_account_id" {
  type        = string
  description = "AWS account ID (passed from the ecs-app root module)."
}

variable "environment" {
  type        = string
  description = "Tenant environment (e.g. dev, uat, prod)."
}

variable "secret_name" {
  type        = string
  description = "Secrets Manager secret name."
  default     = "midas-test-secret-001"
}

variable "secret_string" {
  type        = string
  description = "Initial/current secret value (sensitive; stored in Terraform state)."
  sensitive   = true
}

variable "recovery_window_in_days" {
  type        = number
  description = "Deletion recovery window (0, or 7–30)."
  default     = 7

  validation {
    condition     = var.recovery_window_in_days == 0 || (var.recovery_window_in_days >= 7 && var.recovery_window_in_days <= 30)
    error_message = "recovery_window_in_days must be 0, or between 7 and 30."
  }
}

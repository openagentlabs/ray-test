variable "aws_account_id" {
  type        = string
  description = "AWS account ID (passed from the ecs-app root module)."
}

variable "environment" {
  type        = string
  description = "Tenant environment (e.g. dev, uat, prod) - matches Jenkins TENANT_ENV."
}

variable "aws_region" {
  type        = string
  description = "AWS region (MIDAS: us-east-1 only)."
  default     = "us-east-1"
}

variable "repository_name_suffix" {
  type        = string
  description = "Suffix after midas-{environment}- for the ECR repository name."
  default     = "app"
}

variable "image_tag_mutability" {
  type        = string
  description = "MUTABLE or IMMUTABLE."
  default     = "MUTABLE"

  validation {
    condition     = contains(["MUTABLE", "IMMUTABLE"], var.image_tag_mutability)
    error_message = "image_tag_mutability must be MUTABLE or IMMUTABLE."
  }
}

variable "lifecycle_max_image_count" {
  type        = number
  description = "Expire images when count exceeds this value (keeps newest)."
  default     = 30
}

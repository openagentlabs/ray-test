variable "role_name" {
  description = "Name of the IAM role to create"
  type        = string
  default     = "bti-omf-deployer-role"
}

variable "aws_region" {
  description = "AWS region where the role is created"
  type        = string
  default     = "us-east-1"
}

variable "tags" {
  description = "Tags to apply to deploy role resources"
  type        = map(string)
  default     = {}
}

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
  description = "AWS region"
  default     = "us-east-1"
}

variable "enable_bucket_public_access_block" {
  type        = bool
  description = "When true, create aws_s3_bucket_public_access_block (requires s3:PutBucketPublicAccessBlock). Default false: corporate orgs often deny this API via SCP; rely on account-level Block Public Access + bucket policy + ownership controls instead."
  default     = false
}

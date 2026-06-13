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

variable "vpc_id" {
  type        = string
  description = "VPC ID - use the same as EKS (centrally managed VPC)."
}

variable "subnet_ids" {
  type        = list(string)
  description = "Private subnets for the ElastiCache subnet group - use the same subnets as the EKS managed node group."
}

variable "eks_cluster_security_group_id" {
  type        = string
  description = "EKS cluster security group ID - Redis ingress is allowed from this SG (worker pods/nodes)."
}

variable "additional_ingress_cidrs_all_traffic" {
  type        = list(string)
  description = "Extra CIDRs allowed ingress on all protocols/ports to the ElastiCache security group (e.g. cross-VPC admin hosts). Empty list adds no rules."
  default     = []
}

variable "engine_version" {
  type        = string
  description = "Redis engine version (ElastiCache)."
  default     = "7.1"
}

variable "node_type" {
  type        = string
  description = "ElastiCache node type (dev default: small burstable)."
  default     = "cache.t4g.micro"
}

variable "num_cache_clusters" {
  type        = number
  description = "Number of cache clusters (nodes). Use 1 for single node; 2+ enables automatic failover and requires subnets in multiple AZs."
  default     = 1

  validation {
    condition     = var.num_cache_clusters >= 1 && var.num_cache_clusters <= 6
    error_message = "num_cache_clusters must be between 1 and 6 for this module."
  }
}

variable "secretsmanager_recovery_window_in_days" {
  type        = number
  description = "Secrets Manager deletion recovery window for the Redis auth token secret (0 or 7-30)."
  default     = 7

  validation {
    condition     = var.secretsmanager_recovery_window_in_days == 0 || (var.secretsmanager_recovery_window_in_days >= 7 && var.secretsmanager_recovery_window_in_days <= 30)
    error_message = "secretsmanager_recovery_window_in_days must be 0, or between 7 and 30."
  }
}

variable "tags" {
  type        = map(string)
  description = "Extra tags for ElastiCache resources."
  default     = {}
}

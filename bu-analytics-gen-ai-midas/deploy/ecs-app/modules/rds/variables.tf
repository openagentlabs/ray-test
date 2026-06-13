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

variable "db_subnet_ids" {
  type        = list(string)
  description = "Private subnets for the DB subnet group - use the same subnets as the EKS managed node group."
}

variable "eks_cluster_security_group_id" {
  type        = string
  description = "EKS cluster security group ID - PostgreSQL ingress is allowed from this SG (worker pods/nodes)."
}

variable "additional_ingress_cidrs_all_traffic" {
  type        = list(string)
  description = "Extra CIDRs allowed ingress on all protocols/ports to the RDS security group (e.g. cross-VPC admin hosts). Empty list adds no rules."
  default     = []
}

variable "additional_ingress_cidrs_tcp_5432" {
  type        = list(string)
  description = "CIDRs allowed TCP 5432 only (e.g. workload VPC CIDR so in-VPC VMs and pods can reach PostgreSQL without all-protocol rules). Empty adds no rules."
  default     = []
}

variable "additional_source_security_group_ids_tcp_5432" {
  type        = list(string)
  description = "Extra security group IDs allowed TCP 5432 (optional; e.g. shared data-client SG). Empty adds no rules."
  default     = []
}

variable "engine_version" {
  type        = string
  description = "PostgreSQL engine version (RDS)."
  default     = "15.17"
}

variable "instance_class" {
  type        = string
  description = "RDS instance class (dev default: small burstable)."
  default     = "db.t4g.micro"
}

variable "allocated_storage" {
  type        = number
  description = "Allocated storage (GiB)."
  default     = 20
}

variable "db_name" {
  type        = string
  description = "Initial database name."
  default     = "midas_dev"
}

variable "master_username" {
  type        = string
  description = "Master username (not the password - use manage_master_user_password)."
  default     = "midas_pg"
}

variable "backup_retention_period" {
  type        = number
  description = "Backup retention in days (dev: keep low; prod: 7+)."
  # Fortify "Insufficient RDS Backup": default raised from 1 to 7. Dev tfvars
  # can override down to 1 if cost is a concern; prod stays at the default.
  default = 7
}

# Fortify "Insufficient RDS Monitoring": enhanced monitoring + performance insights.
variable "monitoring_interval" {
  type        = number
  description = "Enhanced monitoring sample interval in seconds (0 disables). 60 is a sensible default."
  default     = 60
}

variable "performance_insights_enabled" {
  type        = bool
  description = "Enable Performance Insights (uses encryption_kms_key_id if set)."
  default     = true
}

variable "performance_insights_retention_period" {
  type        = number
  description = "Performance Insights retention in days (7 = free tier)."
  default     = 7
}

variable "performance_insights_kms_key_id" {
  type        = string
  description = "Optional KMS key ARN for Performance Insights encryption (empty = AWS-managed key)."
  default     = ""
}

variable "skip_final_snapshot" {
  type        = bool
  description = "When true, no final snapshot on destroy (typical for dev)."
  default     = true
}

variable "deletion_protection" {
  type        = bool
  description = "When true, Terraform/API cannot delete the instance without disabling this first."
  # CKV_AWS_293: safe-by-default — callers must explicitly opt out (e.g. dev/test tfvars
  # setting deletion_protection = false) in order to allow `terraform destroy`.
  default = true
}

variable "tags" {
  type        = map(string)
  description = "Extra tags for RDS resources."
  default     = {}
}

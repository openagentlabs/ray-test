variable "environment" {
  description = "Deployment environment (e.g. dev, uat, prod). Used in the domain name and resource names."
  type        = string
}

variable "vpc_id" {
  description = "VPC ID to deploy the OpenSearch domain into. Must be the MIDAS VPC (vpc-0c4d673f3e95a93eb)."
  type        = string
}

variable "vpc_cidr" {
  description = "CIDR block of the MIDAS VPC. Used in the security group ingress rule."
  type        = string
  default     = "10.72.134.0/23"
}

variable "subnet_ids" {
  description = "List of private subnet IDs for the OpenSearch domain VPC config. Provide at least 2 for multi-AZ."
  type        = list(string)
}

variable "opensearch_version" {
  description = "OpenSearch engine version string."
  type        = string
  default     = "OpenSearch_2.11"
}

variable "instance_type" {
  description = "OpenSearch data node instance type."
  type        = string
  default     = "t3.small.search"
}

variable "instance_count" {
  description = "Number of data nodes. Use 1 for dev, 3 for uat/prod (multi-AZ)."
  type        = number
  default     = 1
}

variable "volume_size_gb" {
  description = "EBS gp3 volume size per data node in GiB."
  type        = number
  default     = 20
}

variable "kms_key_arn" {
  description = "Optional KMS CMK ARN for at-rest encryption. Leave empty to use the AWS-managed key."
  type        = string
  default     = ""
}

variable "master_user_arn" {
  description = "IAM ARN to use as the OpenSearch master user (fine-grained access control). Typically the EKS node role ARN."
  type        = string
}

variable "eks_node_role_name" {
  description = "EKS node IAM role name. When set, the OpenSearch write policy is attached so Fluent Bit can bulk-index logs."
  type        = string
  default     = ""
}

variable "retention_in_days" {
  description = "CloudWatch log retention for the OpenSearch audit log group."
  type        = number
  default     = 30
}

variable "tags" {
  description = "Additional tags to merge onto all resources."
  type        = map(string)
  default     = {}
}

# CKV_AWS_318: dedicated master node configuration. Off by default for dev
# (three dedicated master nodes more than double the cluster cost). Set to true
# in production tfvars for HA. Skipped via checkov:skip annotation on the
# domain resource for dev environments.
variable "dedicated_master_enabled" {
  description = "Enable dedicated OpenSearch master nodes (required for production HA, off by default for dev cost)."
  type        = bool
  default     = false
}

variable "dedicated_master_count" {
  description = "Number of dedicated master nodes. Must be 3 or 5 when dedicated_master_enabled is true."
  type        = number
  default     = 3
}

variable "dedicated_master_type" {
  description = "Instance type for the dedicated master nodes."
  type        = string
  default     = "m6g.large.search"
}

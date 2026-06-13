variable "environment" {
  description = "Deployment environment (e.g. dev, uat, prod). Used in workspace alias and resource names."
  type        = string
}

variable "retention_in_days" {
  description = "CloudWatch log retention for the AMP audit log group (created when amp_log_group_arn is empty)."
  type        = number
  default     = 30
}

variable "amp_log_group_arn" {
  description = "ARN of an existing CloudWatch Log Group to use for AMP audit logging. Leave empty to create one automatically."
  type        = string
  default     = ""
}

variable "eks_node_role_name" {
  description = "Name of the EKS node IAM role. When set, the AMP Remote Write policy is attached to this role so the ADOT Collector DaemonSet can push metrics. Leave empty to skip attachment (use IRSA instead)."
  type        = string
  default     = ""
}

variable "tags" {
  description = "Additional tags to merge onto all resources."
  type        = map(string)
  default     = {}
}

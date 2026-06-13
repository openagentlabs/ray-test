variable "role_name" {
  type        = string
  description = "IAM role name for the pod-manager Kubernetes service account (IRSA)."
}

variable "oidc_provider_arn" {
  type        = string
  description = "ARN of the EKS OIDC provider (required for IRSA trust policy)."
}

variable "namespace" {
  type        = string
  default     = "routing"
  description = "Kubernetes namespace of the routing-tier workload."
}

variable "service_account_name" {
  type        = string
  default     = "pod-manager"
  description = "Kubernetes service account name bound to this IAM role."
}

variable "dynamodb_table_arns" {
  type        = list(string)
  description = "DynamoDB table ARNs the workload may access."
}

variable "tags" {
  type        = map(string)
  default     = {}
  description = "Tags applied to the IAM role."
}

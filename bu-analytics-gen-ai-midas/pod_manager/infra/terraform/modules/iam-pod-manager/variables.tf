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

variable "database_url_secret_arn" {
  type        = string
  default     = ""
  description = "Secrets Manager ARN holding the shared Postgres DATABASE_URL. Empty to skip the read policy (e.g. when DSN comes from a Kubernetes Secret)."
}

variable "tags" {
  type        = map(string)
  default     = {}
  description = "Tags applied to the IAM role."
}

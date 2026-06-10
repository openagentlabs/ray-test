variable "application_log_group_arns" {
  description = "Application log group ARNs from cloudwatch_application_logs (Fluent Bit + observability agent may write here)."
  type        = list(string)
  default     = []
  nullable    = false
}

variable "application_log_group_names" {
  description = "Map of service key to application log group name (for dashboard + Fargate log routing)."
  type        = map(string)
  default     = {}
  nullable    = false
}

variable "cluster_name" {
  description = "EKS cluster name."
  type        = string
  nullable    = false
}

variable "fargate_pod_execution_role_arn" {
  description = "Fargate pod execution role ARN (Fluent Bit on Fargate uses this role)."
  type        = string
  nullable    = false
}

variable "fargate_pod_execution_role_name" {
  description = "Fargate pod execution role name for inline logging policy attachment."
  type        = string
  nullable    = false
}

variable "oidc_provider_arn" {
  description = "EKS OIDC provider ARN for IRSA."
  type        = string
  nullable    = false
}

variable "oidc_provider_url" {
  description = "OIDC issuer host without https://."
  type        = string
  nullable    = false
}

variable "retention_in_days" {
  description = "CloudWatch Logs retention for EKS / Container Insights log groups."
  type        = number
  default     = 30
  nullable    = false
}

variable "solution" {
  description = "Solution-wide metadata propagated from the root module."
  type = object({
    name        = string
    description = string
    version     = string
    date        = string
    account_id  = string
    region      = string
  })
  nullable = false
}

variable "subnet_ids" {
  description = "Subnet IDs for CloudWatch addon Fargate profiles."
  type        = list(string)
  nullable    = false
}

variable "application_log_group_arns" {
  description = "Application log group ARNs for observability IAM and Fargate logging."
  type        = list(string)
  default     = []
  nullable    = false
}

variable "application_log_group_names" {
  description = "Map of service key to application log group name."
  type        = map(string)
  default     = {}
  nullable    = false
}

variable "cloudwatch_log_retention_in_days" {
  description = "Retention for EKS / Container Insights log groups."
  type        = number
  default     = 30
  nullable    = false
}

variable "cluster_name" {
  description = "EKS cluster name."
  type        = string
  default     = "arb-ai-assistant"
  nullable    = false
}

variable "namespace" {
  description = "Kubernetes namespace for ARB workloads."
  type        = string
  default     = "arb-ai-assistant"
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

variable "vpc_cidr" {
  description = "CIDR for the dedicated EKS Fargate VPC when creating a new VPC."
  type        = string
  default     = "10.42.0.0/16"
  nullable    = false
}

variable "existing_vpc_id" {
  description = "Reuse an existing VPC instead of creating one."
  type        = string
  default     = ""
  nullable    = false
}

variable "existing_subnet_ids" {
  description = "Public subnet IDs in existing_vpc_id for EKS Fargate."
  type        = list(string)
  default     = []
  nullable    = false
}

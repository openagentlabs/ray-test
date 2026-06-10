variable "cluster_name" {
  description = "EKS cluster name."
  type        = string
  default     = "arb-ai-assistant"
  nullable    = false
}

variable "kubernetes_version" {
  description = "EKS control plane version."
  type        = string
  default     = "1.31"
  nullable    = false
}

variable "namespace" {
  description = "Kubernetes namespace for ARB workloads (Fargate profile selector)."
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

variable "control_plane_log_types" {
  description = "EKS control plane log types shipped to CloudWatch Logs."
  type        = list(string)
  default     = ["api", "audit", "authenticator", "controllerManager", "scheduler"]
  nullable    = false
}

variable "log_retention_in_days" {
  description = "Retention for the EKS control plane CloudWatch log group."
  type        = number
  default     = 30
  nullable    = false
}

variable "subnet_ids" {
  description = "Subnet IDs for the EKS cluster control plane."
  type        = list(string)
  nullable    = false
}

variable "fargate_subnet_ids" {
  description = "Private subnet IDs for EKS Fargate profiles."
  type        = list(string)
  nullable    = false
}

variable "vpc_id" {
  description = "VPC ID hosting the EKS cluster."
  type        = string
  nullable    = false
}

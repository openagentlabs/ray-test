variable "cluster_name" {
  description = "EKS cluster name."
  type        = string
  default     = "ray-test"
  nullable    = false
}

variable "kubernetes_version" {
  description = "EKS control plane version."
  type        = string
  default     = "1.36"
  nullable    = false
}

variable "namespace" {
  description = "Kubernetes namespace for ARB workloads (Fargate profile selector)."
  type        = string
  default     = "ray-test"
  nullable    = false
}

variable "fargate_workloads_namespace_enabled" {
  description = "When true, schedule the workloads namespace on Fargate. Disable when all workloads use EC2 (e.g. manager-web with FSx/S3 mounts)."
  type        = bool
  default     = true
  nullable    = false
}

variable "solution" {
  description = "Solution-wide metadata propagated from the root module."
  type = object({
    name                   = string
    description            = string
    version                = string
    date                   = string
    account_id             = string
    region                 = string
    deployment_environment = string
    deployment_index       = string
    deployment_instance    = string
    deployment_key         = string
    deployed_at            = string
    deployed_by            = string
    expires_at             = string
    cost_code              = string
    department             = string
  })
  nullable = false
}

variable "cluster_security_group_ids" {
  description = "Additional security group IDs attached to the EKS cluster ENI (least-privilege network segmentation)."
  type        = list(string)
  default     = []
  nullable    = false
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

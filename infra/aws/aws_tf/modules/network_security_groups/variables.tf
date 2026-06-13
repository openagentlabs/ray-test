variable "alb_ingress_cidr_blocks" {
  description = "CIDR blocks allowed to reach the public ALB on HTTP/HTTPS."
  type        = list(string)
  default     = ["0.0.0.0/0"]
  nullable    = false
}

variable "bastion_ssh_cidr_blocks" {
  description = "Optional CIDR blocks for SSH to bastion (empty disables SSH ingress; prefer SSM Session Manager)."
  type        = list(string)
  default     = []
  nullable    = false
}

variable "cluster_name" {
  description = "EKS cluster name for security group descriptions."
  type        = string
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

variable "vpc_cidr_block" {
  description = "VPC CIDR for intra-VPC and health-check rules."
  type        = string
  nullable    = false
}

variable "vpc_id" {
  description = "VPC ID where security groups are created."
  type        = string
  nullable    = false
}

variable "workload_container_ports" {
  description = "TCP ports on EKS workloads that the ALB may forward traffic to."
  type        = list(number)
  default     = [8802, 8803, 8804, 8805, 8806, 8807, 8808, 8809, 8810, 8811]
  nullable    = false
}

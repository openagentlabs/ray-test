variable "availability_zone_count" {
  description = "Number of availability zones to span (minimum 2 for EKS and ALB)."
  type        = number
  default     = 2
  nullable    = false

  validation {
    condition     = var.availability_zone_count >= 2 && var.availability_zone_count <= 3
    error_message = "availability_zone_count must be between 2 and 3."
  }
}

variable "cluster_name" {
  description = "EKS cluster name for subnet tagging (empty skips kubernetes.io/cluster tags)."
  type        = string
  default     = ""
  nullable    = false
}

variable "existing_subnet_ids" {
  description = "Public subnet IDs in existing_vpc_id when reusing a VPC (legacy; minimum two AZs)."
  type        = list(string)
  default     = []
  nullable    = false
}

variable "existing_vpc_id" {
  description = "Reuse an existing VPC instead of creating one (required when account VPC quota is exhausted)."
  type        = string
  default     = ""
  nullable    = false
}

variable "single_nat_gateway_enabled" {
  description = "When true, provision one NAT gateway (cost-efficient). When false, one NAT per AZ (HA)."
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

variable "vpc_cidr" {
  description = "CIDR for the platform VPC when creating a new VPC."
  type        = string
  default     = "10.42.0.0/16"
  nullable    = false
}

variable "vpc_endpoints_enabled" {
  description = "Create interface and gateway VPC endpoints for private EKS/bastion connectivity (ECR, S3, SSM, Logs)."
  type        = bool
  default     = true
  nullable    = false
}

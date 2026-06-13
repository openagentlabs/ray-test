variable "cluster_name" {
  description = "EKS cluster name the node group joins."
  type        = string
  nullable    = false
}

variable "node_count" {
  description = "Fixed number of EC2 worker nodes (min=desired=max)."
  type        = number
  default     = 3
  nullable    = false

  validation {
    condition     = var.node_count >= 1 && var.node_count <= 10
    error_message = "node_count must be between 1 and 10."
  }
}

variable "node_instance_type" {
  description = "EC2 instance type for Ray / demo workloads (8 vCPU / 32 GiB default: m6i.2xlarge)."
  type        = string
  default     = "m6i.2xlarge"
  nullable    = false
}

variable "node_pool_label_key" {
  description = "Kubernetes node label key used to schedule Ray and demo pods."
  type        = string
  default     = "ray.io/node-pool"
  nullable    = false
}

variable "node_pool_label_value" {
  description = "Kubernetes node label value for the Ray compute pool."
  type        = string
  default     = "ray"
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

variable "cluster_certificate_authority_data" {
  description = "Base64-encoded CA certificate for the EKS API (nodeadm bootstrap when install_lustre_client is true)."
  type        = string
  default     = ""
  nullable    = false
}

variable "cluster_endpoint" {
  description = "EKS API server endpoint (nodeadm bootstrap when install_lustre_client is true)."
  type        = string
  default     = ""
  nullable    = false
}

variable "cluster_service_ipv4_cidr" {
  description = "Kubernetes service IPv4 CIDR (nodeadm bootstrap when install_lustre_client is true)."
  type        = string
  default     = ""
  nullable    = false
}

variable "install_lustre_client" {
  description = "When true, launch template user_data installs lustre-client on AL2023 nodes (required for FSx CSI mounts)."
  type        = bool
  default     = false
  nullable    = false
}

variable "subnet_ids" {
  description = "Private subnet IDs for the managed node group."
  type        = list(string)
  nullable    = false
}

variable "cluster_security_group_id" {
  description = "EKS cluster security group ID (required on Ray node ENIs for control plane and FSx Lustre client access)."
  type        = string
  nullable    = false
}

variable "additional_security_group_ids" {
  description = "Extra security groups for Ray node ENIs (for example eks_workloads SG for ALB and FSx ingress rules)."
  type        = list(string)
  default     = []
  nullable    = false
}

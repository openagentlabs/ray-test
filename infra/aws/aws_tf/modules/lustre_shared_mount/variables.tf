variable "chart_version" {
  description = "Helm chart version for the AWS FSx CSI driver."
  type        = string
  default     = "1.9.0"
  nullable    = false
}

variable "cluster_name" {
  description = "EKS cluster name hosting the FSx CSI driver."
  type        = string
  nullable    = false
}

variable "file_system_dns_name" {
  description = "DNS name of the FSx for Lustre file system."
  type        = string
  nullable    = false
}

variable "file_system_id" {
  description = "Identifier of the FSx for Lustre file system (for example fs-12345678)."
  type        = string
  nullable    = false
}

variable "file_system_mount_name" {
  description = "Lustre mount name returned by the FSx API."
  type        = string
  nullable    = false
}

variable "mount_namespaces" {
  description = "Kubernetes namespaces that receive a shared-lustre PVC bound to the same FSx file system."
  type        = list(string)
  nullable    = false
}

variable "node_pool_label_key" {
  description = "Node label key for EC2 compute pool (FSx CSI node DaemonSet schedules only on these nodes)."
  type        = string
  default     = "ray.io/node-pool"
  nullable    = false
}

variable "node_pool_label_value" {
  description = "Node label value for EC2 compute pool."
  type        = string
  default     = "ray"
  nullable    = false
}

variable "oidc_provider_arn" {
  description = "IAM OIDC provider ARN for IRSA."
  type        = string
  nullable    = false
}

variable "oidc_provider_url" {
  description = "OIDC issuer host (without https://) for IRSA trust policies."
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

variable "storage_capacity_gib" {
  description = "Provisioned FSx for Lustre capacity in GiB (must match the Terraform file system)."
  type        = number
  nullable    = false
}

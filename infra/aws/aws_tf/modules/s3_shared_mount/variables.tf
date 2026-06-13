variable "addon_version" {
  description = "EKS add-on version for aws-mountpoint-s3-csi-driver (empty uses latest compatible)."
  type        = string
  default     = ""
  nullable    = false
}

variable "bucket_arn" {
  description = "ARN of the shared S3 bucket to mount."
  type        = string
  nullable    = false
}

variable "bucket_key_prefix" {
  description = "S3 key prefix mounted into pods (trailing slash recommended)."
  type        = string
  default     = "shared/"
  nullable    = false
}

variable "bucket_name" {
  description = "Name of the shared S3 bucket to mount."
  type        = string
  nullable    = false
}

variable "cluster_name" {
  description = "EKS cluster name hosting the Mountpoint S3 CSI driver."
  type        = string
  nullable    = false
}

variable "mount_namespaces" {
  description = "Kubernetes namespaces that receive a shared-s3-files PVC bound to the same bucket."
  type        = list(string)
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

variable "storage_request_gib" {
  description = "PVC storage request in GiB (ignored by S3 CSI but required by Kubernetes)."
  type        = number
  default     = 1200
  nullable    = false
}

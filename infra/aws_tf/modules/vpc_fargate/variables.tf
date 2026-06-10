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

variable "cluster_name" {
  description = "EKS cluster name for subnet tagging (empty skips kubernetes.io/cluster tags)."
  type        = string
  default     = ""
  nullable    = false
}

variable "vpc_cidr" {
  description = "CIDR for the dedicated EKS Fargate VPC when creating a new VPC."
  type        = string
  default     = "10.42.0.0/16"
  nullable    = false
}

variable "existing_vpc_id" {
  description = "Reuse an existing VPC instead of creating one (required when account VPC quota is exhausted)."
  type        = string
  default     = ""
  nullable    = false
}

variable "existing_subnet_ids" {
  description = "Public subnet IDs in existing_vpc_id for EKS Fargate (minimum two AZs)."
  type        = list(string)
  default     = []
  nullable    = false
}

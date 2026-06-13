variable "chart_version" {
  description = "Helm chart version for the KubeRay operator."
  type        = string
  default     = "1.6.1"
  nullable    = false
}

variable "namespace" {
  description = "Kubernetes namespace for the KubeRay operator and RayCluster."
  type        = string
  default     = "kuberay"
  nullable    = false
}

variable "node_pool_label_key" {
  description = "Node label key for scheduling the operator onto Ray EC2 nodes."
  type        = string
  nullable    = false
}

variable "node_pool_label_value" {
  description = "Node label value for scheduling the operator onto Ray EC2 nodes."
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

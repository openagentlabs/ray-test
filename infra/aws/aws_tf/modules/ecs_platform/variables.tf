variable "subnet_ids" {
  description = "Subnet IDs for Fargate tasks and public ALBs."
  type        = list(string)
  nullable    = false
}

variable "vpc_id" {
  description = "VPC id for ECS cluster networking and Cloud Map."
  type        = string
  nullable    = false
}

variable "service_discovery_namespace_name" {
  description = "Private DNS namespace for ECS service discovery (e.g. arb-ai-assistant.local)."
  type        = string
  nullable    = false
}

variable "cluster_name" {
  description = "ECS cluster name."
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

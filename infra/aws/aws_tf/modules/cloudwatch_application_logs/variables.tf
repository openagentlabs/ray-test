variable "solution" {
  description = "Solution-wide metadata propagated from the root module (see infras/resource-naming.mdc deployment_key)."
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

variable "retention_in_days" {
  description = "CloudWatch Logs retention for application log groups."
  type        = number
  nullable    = false
  default     = 30
}

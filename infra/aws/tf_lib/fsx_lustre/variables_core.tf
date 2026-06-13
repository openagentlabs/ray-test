###############################################################################
# infra/tf_lib/fsx_lustre — core inputs
#
# Adapted from terraform-aws-modules/fsx/aws//modules/lustre v1.3.1
# (https://registry.terraform.io/modules/terraform-aws-modules/fsx/aws/latest/submodules/lustre)
###############################################################################

variable "additional_tags" {
  description = "Extra tags merged on top of module tags."
  type        = map(string)
  default     = {}
  nullable    = false
}

variable "create" {
  description = "When false, skip creating FSx for Lustre resources."
  type        = bool
  default     = true
  nullable    = false
}

variable "purpose" {
  description = <<-EOT
    Short purpose suffix for the file system name:

        <solution.name>-<purpose>

    Lower snake or kebab; underscores normalized to hyphens in `local.file_system_name`.
  EOT
  type        = string
  nullable    = false

  validation {
    condition     = can(regex("^[a-z][a-z0-9_-]*[a-z0-9]$", var.purpose))
    error_message = "purpose must be lower_snake or lower_kebab, start with a letter, end alphanumeric."
  }
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
  description = "VPC CIDR allowed to mount the file system (EKS nodes and Fargate ENIs)."
  type        = string
  nullable    = false
}

variable "workload_security_group_ids" {
  description = "Optional extra security group IDs (for example EKS workload ENI groups) allowed Lustre client access."
  type        = list(string)
  default     = []
  nullable    = false
}

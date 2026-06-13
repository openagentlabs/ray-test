###############################################################################
# infra/tf_lib/iam_role — inputs
#
# Add or change permissions by editing this module (e.g. add
# `aws_iam_role_policy` / `aws_iam_role_policy_attachment` blocks) or by passing
# additional managed policy ARNs. Trust and name stay parameterized.
###############################################################################

variable "additional_tags" {
  description = "Extra tags merged onto the IAM role in addition to provider default_tags."
  type        = map(string)
  default     = {}
  nullable    = false
}

variable "assume_role_policy_json" {
  description = "JSON trust policy for `aws_iam_role.assume_role_policy` (who may call sts:AssumeRole)."
  type        = string
  nullable    = false
}

variable "description" {
  description = "Optional IAM role description (shown in the console)."
  type        = string
  default     = null
  nullable    = true
}

variable "managed_policy_arns" {
  description = "AWS managed or customer managed policy ARNs to attach to the role."
  type        = list(string)
  default     = []
  nullable    = false
}

variable "max_session_duration" {
  description = "Maximum session duration (seconds) for assumed role sessions (3600–43200)."
  type        = number
  default     = 3600
  nullable    = false

  validation {
    condition     = var.max_session_duration >= 3600 && var.max_session_duration <= 43200
    error_message = "max_session_duration must be between 3600 and 43200 seconds."
  }
}

variable "path" {
  description = "IAM path prefix for the role (e.g. \"/system/\")."
  type        = string
  default     = "/"
  nullable    = false
}

variable "role_name" {
  description = "IAM role name (set per stack; must be unique in the account)."
  type        = string
  nullable    = false
}

variable "solution" {
  description = <<-EOT
    Solution-wide metadata propagated from the root module (same shape as other
    child modules in this repo).
  EOT
  type = object({
    name        = string
    description = string
    version     = string
    date        = string
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

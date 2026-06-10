###############################################################################
# infra/aws_tf/modules/iam_admin_role — inputs
###############################################################################

variable "role_name" {
  description = "IAM role name for the account administrator role (default matches project convention)."
  type        = string
  default     = "arb-admin-role"
  nullable    = false
}

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

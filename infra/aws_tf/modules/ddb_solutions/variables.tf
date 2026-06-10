###############################################################################
# infra/aws_tf/modules/ddb_solutions — inputs
###############################################################################

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

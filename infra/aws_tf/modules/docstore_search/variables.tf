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

variable "opensearch_principal_arns" {
  description = "IAM principal ARNs granted data access to the docstore OpenSearch collection."
  type        = list(string)
  default     = []
  nullable    = false
}

variable "image_tag_mutability" {
  description = "MUTABLE is lower cost for iterative pushes; IMMUTABLE for production pins."
  type        = string
  default     = "MUTABLE"
  nullable    = false
}

variable "keep_tagged_image_count" {
  description = "Maximum tagged images to retain (lifecycle policy)."
  type        = number
  default     = 10
  nullable    = false
}

variable "repository_name" {
  description = "ECR repository name (unique per account/region)."
  type        = string
  nullable    = false
}

variable "scan_on_push" {
  description = "Enable basic scan-on-push (no enhanced scanning cost tier)."
  type        = bool
  default     = true
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

variable "workload_key" {
  description = "Stable workload identifier for tags (e.g. iam_svc, frontend)."
  type        = string
  nullable    = false
}

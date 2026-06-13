variable "repository_names" {
  type        = list(string)
  description = "ECR repository names to create."
}

variable "image_tag_mutability" {
  type        = string
  default     = "MUTABLE"
  description = "MUTABLE or IMMUTABLE."
}

variable "scan_on_push" {
  type        = bool
  default     = true
  description = "Enable image scanning on push."
}

variable "lifecycle_max_image_count" {
  type        = number
  default     = 30
  description = "Expire images beyond this count per repository."
}

variable "force_delete" {
  type        = bool
  default     = true
  description = "Delete repository and all images on terraform destroy (avoids RepositoryNotEmptyException)."
}

variable "tags" {
  type        = map(string)
  default     = {}
  description = "Tags applied to ECR repositories."
}

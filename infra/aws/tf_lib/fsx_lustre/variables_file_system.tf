variable "automatic_backup_retention_days" {
  description = "Automatic backup retention days for PERSISTENT_* deployment types (0 disables)."
  type        = number
  default     = 0
  nullable    = false
}

variable "data_compression_type" {
  description = "Data compression type: LZ4 or NONE."
  type        = string
  default     = "NONE"
  nullable    = false

  validation {
    condition     = contains(["LZ4", "NONE"], var.data_compression_type)
    error_message = "data_compression_type must be LZ4 or NONE."
  }
}

variable "deployment_type" {
  description = "FSx for Lustre deployment type."
  type        = string
  default     = "PERSISTENT_2"
  nullable    = false

  validation {
    condition     = contains(["SCRATCH_1", "SCRATCH_2", "PERSISTENT_1", "PERSISTENT_2"], var.deployment_type)
    error_message = "deployment_type must be SCRATCH_1, SCRATCH_2, PERSISTENT_1, or PERSISTENT_2."
  }
}

variable "per_unit_storage_throughput" {
  description = "Read/write throughput in MB/s/TiB for PERSISTENT_* deployment types."
  type        = number
  default     = 125
  nullable    = false
}

variable "storage_capacity" {
  description = "File system storage capacity in GiB (minimum 1200 for most deployment types)."
  type        = number
  default     = 1200
  nullable    = false

  validation {
    condition     = var.storage_capacity >= 1200
    error_message = "storage_capacity must be at least 1200 GiB."
  }
}

variable "storage_type" {
  description = "Storage type for PERSISTENT_* deployment types."
  type        = string
  default     = "SSD"
  nullable    = false

  validation {
    condition     = contains(["SSD", "HDD", "INTELLIGENT_TIERING"], var.storage_type)
    error_message = "storage_type must be SSD, HDD, or INTELLIGENT_TIERING."
  }
}

variable "subnet_ids" {
  description = "Subnet IDs for FSx for Lustre (single-AZ; use the first EKS private subnet)."
  type        = list(string)
  nullable    = false

  validation {
    condition     = length(var.subnet_ids) >= 1
    error_message = "subnet_ids must include at least one subnet ID."
  }
}

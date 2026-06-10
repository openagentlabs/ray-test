###############################################################################
# infra/tf_lib/dynamodb — global secondary indexes
###############################################################################

variable "global_secondary_indexes" {
  description = <<-EOT
    Optional list of GSIs. Each entry defines `name`, `hash_key` and optional
    `range_key` (same `{ name, type }` shape as the table keys),
    `projection_type` (ALL | KEYS_ONLY | INCLUDE), optional
    `non_key_attributes` for INCLUDE, and optional `read_capacity` /
    `write_capacity` when the table uses PROVISIONED billing (ignored for
    on-demand).
  EOT
  type = list(object({
    name               = string
    hash_key           = object({ name = string, type = string })
    range_key          = optional(object({ name = string, type = string }), null)
    projection_type    = string
    non_key_attributes = optional(list(string), [])
    read_capacity      = optional(number, null)
    write_capacity     = optional(number, null)
  }))
  default  = []
  nullable = false

  validation {
    condition = alltrue([
      for g in var.global_secondary_indexes : contains(["ALL", "KEYS_ONLY", "INCLUDE"], g.projection_type)
    ])
    error_message = "Each global_secondary_indexes.projection_type must be ALL, KEYS_ONLY, or INCLUDE."
  }

  validation {
    condition = alltrue([
      for g in var.global_secondary_indexes : contains(["S", "N", "B"], g.hash_key.type)
    ])
    error_message = "Each GSI hash_key.type must be S, N, or B."
  }

  validation {
    condition = alltrue([
      for g in var.global_secondary_indexes : try(g.range_key, null) == null || contains(["S", "N", "B"], g.range_key.type)
    ])
    error_message = "Each GSI range_key.type must be S, N, or B when range_key is set."
  }
}

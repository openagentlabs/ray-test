###############################################################################
# infra/tf_lib/dynamodb — primary key schema
# Variables in this file: alphabetical order.
###############################################################################

variable "hash_key" {
  description = <<-EOT
    Table partition key: `name` (1–255 chars) and DynamoDB scalar `type`
    (`S`, `N`, or `B`).
  EOT
  type = object({
    name = string
    type = string
  })
  nullable = false

  validation {
    condition     = contains(["S", "N", "B"], var.hash_key.type)
    error_message = "hash_key.type must be S, N, or B."
  }
}

variable "range_key" {
  description = <<-EOT
    Optional sort key for the table. Same shape as `hash_key`; null if the
    table is partition-key only.
  EOT
  type = object({
    name = string
    type = string
  })
  default  = null
  nullable = true

  validation {
    condition     = var.range_key == null || contains(["S", "N", "B"], var.range_key.type)
    error_message = "range_key.type must be S, N, or B when range_key is set."
  }
}

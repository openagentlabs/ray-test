###############################################################################
# infra/tf_lib/dynamodb — primary table resource
###############################################################################

resource "aws_dynamodb_table" "this" {
  name                        = local.table_name
  billing_mode                = var.billing_mode
  hash_key                    = var.hash_key.name
  range_key                   = try(var.range_key.name, null)
  read_capacity               = var.billing_mode == "PROVISIONED" ? var.read_capacity : null
  write_capacity              = var.billing_mode == "PROVISIONED" ? var.write_capacity : null
  stream_enabled              = var.stream_enabled
  stream_view_type            = var.stream_enabled ? var.stream_view_type : null
  deletion_protection_enabled = var.deletion_protection_enabled
  table_class                 = var.table_class

  dynamic "attribute" {
    for_each = local.attribute_definitions_final
    content {
      name = attribute.value.name
      type = attribute.value.type
    }
  }

  point_in_time_recovery {
    enabled = var.point_in_time_recovery_enabled
  }

  dynamic "server_side_encryption" {
    for_each = var.customer_managed_encryption_enabled ? [1] : []
    content {
      enabled     = true
      kms_key_arn = var.kms_key_arn
    }
  }

  dynamic "ttl" {
    for_each = var.ttl_enabled ? [1] : []
    content {
      enabled        = true
      attribute_name = var.ttl_attribute_name
    }
  }

  dynamic "global_secondary_index" {
    for_each = var.global_secondary_indexes
    content {
      name               = global_secondary_index.value.name
      hash_key           = global_secondary_index.value.hash_key.name
      range_key          = try(global_secondary_index.value.range_key.name, null)
      projection_type    = global_secondary_index.value.projection_type
      non_key_attributes = global_secondary_index.value.projection_type == "INCLUDE" ? global_secondary_index.value.non_key_attributes : null
      read_capacity = var.billing_mode == "PROVISIONED" ? coalesce(
        global_secondary_index.value.read_capacity,
        var.read_capacity,
      ) : null
      write_capacity = var.billing_mode == "PROVISIONED" ? coalesce(
        global_secondary_index.value.write_capacity,
        var.write_capacity,
      ) : null
    }
  }

  tags = local.module_tags
}

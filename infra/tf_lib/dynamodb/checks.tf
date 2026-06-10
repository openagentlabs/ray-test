###############################################################################
# infra/tf_lib/dynamodb — cross-variable checks (Terraform 1.5+)
###############################################################################

check "provisioned_requires_capacities" {
  assert {
    condition = (
      var.billing_mode != "PROVISIONED"
      ) || (
      var.read_capacity != null && var.read_capacity > 0 &&
      var.write_capacity != null && var.write_capacity > 0
    )
    error_message = "billing_mode PROVISIONED requires read_capacity and write_capacity as positive numbers."
  }
}

check "cmk_requires_kms_arn" {
  assert {
    condition = (
      !var.customer_managed_encryption_enabled
      ) || (
      var.kms_key_arn != null && var.kms_key_arn != ""
    )
    error_message = "customer_managed_encryption_enabled requires a non-empty kms_key_arn."
  }
}

check "ttl_requires_attribute" {
  assert {
    condition     = !var.ttl_enabled || (var.ttl_attribute_name != null && var.ttl_attribute_name != "")
    error_message = "ttl_enabled requires ttl_attribute_name to be set."
  }
}

check "stream_requires_view_type" {
  assert {
    condition = (
      !var.stream_enabled
      ) || (
      var.stream_view_type != null && contains(
        ["KEYS_ONLY", "NEW_IMAGE", "OLD_IMAGE", "NEW_AND_OLD_IMAGES"],
        var.stream_view_type,
      )
    )
    error_message = "stream_enabled requires stream_view_type to be KEYS_ONLY, NEW_IMAGE, OLD_IMAGE, or NEW_AND_OLD_IMAGES."
  }
}

check "attribute_key_types_consistent" {
  assert {
    condition = alltrue([
      for n in local.attribute_names :
      length(distinct([for a in local.all_attrs_raw : a.type if a.name == n])) == 1
    ])
    error_message = "The same attribute name cannot be declared with conflicting DynamoDB types (S/N/B) across the table and GSIs."
  }
}

check "gsi_include_requires_non_key_attributes" {
  assert {
    condition = alltrue([
      for g in var.global_secondary_indexes :
      g.projection_type != "INCLUDE" || length(coalesce(g.non_key_attributes, [])) > 0
    ])
    error_message = "Each GSI with projection_type INCLUDE must set non_key_attributes to a non-empty list of attribute names."
  }
}

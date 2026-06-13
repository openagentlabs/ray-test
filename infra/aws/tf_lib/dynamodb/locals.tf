###############################################################################
# infra/tf_lib/dynamodb — locals
#
# Default posture: on-demand billing, no streams, no TTL, no PITR, no CMK,
# no deletion protection — suitable for a minimal private app table. Turn
# features on explicitly via variables (all booleans default false).
###############################################################################

locals {
  table_name = replace(replace(replace(lower(replace(
    "${var.solution.name}-${var.solution.deployment_key}-${var.purpose}-${var.solution.account_id}",
    "_",
    "-",
  )), "--", "-"), "--", "-"), "--", "-")

  module_tags = merge(
    {
      "ddb:Purpose" = var.purpose
    },
    var.additional_tags,
  )

  # Flatten GSI partition/sort key attribute objects for uniqueness merge.
  gsi_key_attrs = flatten([
    for g in var.global_secondary_indexes : concat(
      [g.hash_key],
      try(g.range_key, null) != null ? [g.range_key] : [],
    )
  ])

  all_attrs_raw = concat(
    [var.hash_key],
    var.range_key != null ? [var.range_key] : [],
    local.gsi_key_attrs,
  )

  attribute_names = distinct([for a in local.all_attrs_raw : a.name])

  attribute_definitions_final = [
    for n in local.attribute_names : {
      name = n
      type = [for a in local.all_attrs_raw : a if a.name == n][0].type
    }
  ]
}

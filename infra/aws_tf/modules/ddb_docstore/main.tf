###############################################################################
# document-storage.svc — registry and groups tables.
###############################################################################

module "docstore_registry" {
  source = "../ddb_app_data"

  solution = var.solution
  purpose  = "docstore-registry"

  hash_key = {
    name = "id"
    type = "S"
  }

  global_secondary_indexes = [
    {
      name            = "tables-by-slug"
      hash_key        = { name = "group_id", type = "S" }
      range_key       = { name = "slug", type = "S" }
      projection_type = "ALL"
    },
    {
      name            = "tables-by-name"
      hash_key        = { name = "group_id", type = "S" }
      range_key       = { name = "name", type = "S" }
      projection_type = "ALL"
    },
  ]
}

module "docstore_groups" {
  source = "../ddb_app_data"

  solution = var.solution
  purpose  = "docstore-groups"

  hash_key = {
    name = "id"
    type = "S"
  }

  global_secondary_indexes = [
    {
      name            = "groups-by-slug"
      hash_key        = { name = "slug", type = "S" }
      projection_type = "ALL"
    },
  ]
}

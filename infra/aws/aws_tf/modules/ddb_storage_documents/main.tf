###############################################################################
# storage.svc — document file registry (PK path, SK file_name; GSI id-index).
###############################################################################

module "document_files" {
  source = "../ddb_app_data"

  solution = var.solution
  purpose  = "storage-document-files"

  hash_key = {
    name = "path"
    type = "S"
  }

  range_key = {
    name = "file_name"
    type = "S"
  }

  global_secondary_indexes = [
    {
      name            = "id-index"
      hash_key        = { name = "id", type = "S" }
      projection_type = "ALL"
    },
  ]
}

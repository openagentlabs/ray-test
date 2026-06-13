###############################################################################
# requirements.svc — requirement documents, rows, and import jobs.
###############################################################################

module "requirement_documents" {
  source = "../ddb_app_data"

  solution = var.solution
  purpose  = "requirement-documents"

  hash_key = {
    name = "id"
    type = "S"
  }

  global_secondary_indexes = [
    {
      name            = "documents-by-name"
      hash_key        = { name = "name", type = "S" }
      projection_type = "ALL"
    },
  ]
}

module "requirement_document_rows" {
  source = "../ddb_app_data"

  solution = var.solution
  purpose  = "requirement-document-rows"

  hash_key = {
    name = "document_id"
    type = "S"
  }

  range_key = {
    name = "row_id"
    type = "S"
  }

  global_secondary_indexes = [
    {
      name            = "rows-by-sort-order"
      hash_key        = { name = "document_id", type = "S" }
      range_key       = { name = "sort_order", type = "N" }
      projection_type = "ALL"
    },
  ]
}

module "requirement_import_jobs" {
  source = "../ddb_app_data"

  solution = var.solution
  purpose  = "requirement-import-jobs"

  hash_key = {
    name = "id"
    type = "S"
  }

  global_secondary_indexes = [
    {
      name            = "jobs-by-document"
      hash_key        = { name = "document_id", type = "S" }
      projection_type = "ALL"
    },
  ]
}

###############################################################################
# ARB solution owner data — DynamoDB tables using ../ddb_app_data template.
# solutions: PK id; GSI owner-solutions (owner_user_id, updated_at) for listing.
# Item attributes (non-exhaustive): state (S), approved (BOOL|null omitted), current_stage (S), ai (S), …
# solution_history: PK solution_id, SK entry_id — append-only activity log.
# solution_documents: PK id; GSI solution-documents (solution_id) — document metadata + storage path.
###############################################################################

module "solutions" {
  source = "../ddb_app_data"

  solution = var.solution
  purpose  = "arb-solutions"

  hash_key = {
    name = "id"
    type = "S"
  }

  global_secondary_indexes = [
    {
      name            = "owner-solutions"
      hash_key        = { name = "owner_user_id", type = "S" }
      projection_type = "ALL"
    },
  ]
}

module "solution_history" {
  source = "../ddb_app_data"

  solution = var.solution
  purpose  = "arb-solution-history"

  hash_key = {
    name = "solution_id"
    type = "S"
  }

  range_key = {
    name = "entry_id"
    type = "S"
  }
}

module "solution_documents" {
  source = "../ddb_app_data"

  solution = var.solution
  purpose  = "arb-solution-documents"

  hash_key = {
    name = "id"
    type = "S"
  }

  global_secondary_indexes = [
    {
      name            = "solution-documents"
      hash_key        = { name = "solution_id", type = "S" }
      projection_type = "ALL"
    },
  ]
}

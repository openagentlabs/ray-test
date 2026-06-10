###############################################################################
# arch.diagram.agent.svc — conversion jobs (PK id; GSI jobs-by-status).
###############################################################################

module "conversion_jobs" {
  source = "../ddb_app_data"

  solution = var.solution
  purpose  = "arch-diagram-conversion-jobs"

  hash_key = {
    name = "id"
    type = "S"
  }

  global_secondary_indexes = [
    {
      name            = "jobs-by-status"
      hash_key        = { name = "status", type = "S" }
      range_key       = { name = "created_at", type = "S" }
      projection_type = "ALL"
    },
  ]
}

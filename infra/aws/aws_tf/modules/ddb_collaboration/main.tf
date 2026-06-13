###############################################################################
# collaboration.svc — DynamoDB tables using ../ddb_app_data template.
# resource_aliases: PK alias; GSI entity-aliases (entity_type, entity_id).
# discussion_threads: PK id; GSI context-threads (context_type, context_id).
# discussion_messages: PK thread_id, SK message_id.
###############################################################################

module "resource_aliases" {
  source = "../ddb_app_data"

  solution = var.solution
  purpose  = "arb-resource-aliases"

  hash_key = {
    name = "alias"
    type = "S"
  }

  global_secondary_indexes = [
    {
      name            = "entity-aliases"
      hash_key        = { name = "entity_type", type = "S" }
      range_key       = { name = "entity_id", type = "S" }
      projection_type = "ALL"
    },
  ]
}

module "discussion_threads" {
  source = "../ddb_app_data"

  solution = var.solution
  purpose  = "arb-discussion-threads"

  hash_key = {
    name = "id"
    type = "S"
  }

  global_secondary_indexes = [
    {
      name            = "context-threads"
      hash_key        = { name = "context_type", type = "S" }
      range_key       = { name = "context_id", type = "S" }
      projection_type = "ALL"
    },
  ]
}

module "discussion_messages" {
  source = "../ddb_app_data"

  solution = var.solution
  purpose  = "arb-discussion-messages"

  hash_key = {
    name = "thread_id"
    type = "S"
  }

  range_key = {
    name = "message_id"
    type = "S"
  }
}

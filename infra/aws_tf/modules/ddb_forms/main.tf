###############################################################################
# ARB form templates, instances, assignments, collaborator groups, audit.
###############################################################################

module "form_groups" {
  source   = "../ddb_app_data"
  solution = var.solution
  purpose  = "arb-form-groups"

  hash_key = { name = "id", type = "S" }
}

module "form_templates" {
  source   = "../ddb_app_data"
  solution = var.solution
  purpose  = "arb-form-templates"

  hash_key = { name = "id", type = "S" }

  global_secondary_indexes = [
    {
      name            = "form-group-forms"
      hash_key        = { name = "form_group_id", type = "S" }
      projection_type = "ALL"
    },
  ]
}

module "form_template_questions" {
  source   = "../ddb_app_data"
  solution = var.solution
  purpose  = "arb-form-template-questions"

  hash_key = { name = "id", type = "S" }

  global_secondary_indexes = [
    {
      name            = "form-template-questions"
      hash_key        = { name = "form_template_id", type = "S" }
      range_key       = { name = "sort_order", type = "N" }
      projection_type = "ALL"
    },
  ]
}

module "solution_owner_forms" {
  source   = "../ddb_app_data"
  solution = var.solution
  purpose  = "arb-solution-owner-forms"

  hash_key = { name = "id", type = "S" }

  global_secondary_indexes = [
    {
      name            = "solution-forms"
      hash_key        = { name = "registered_solution_id", type = "S" }
      projection_type = "ALL"
    },
    {
      name            = "owner-forms"
      hash_key        = { name = "solution_owner_user_id", type = "S" }
      projection_type = "ALL"
    },
  ]
}

module "solution_owner_form_content" {
  source   = "../ddb_app_data"
  solution = var.solution
  purpose  = "arb-solution-owner-form-content"

  hash_key = { name = "id", type = "S" }

  global_secondary_indexes = [
    {
      name            = "form-content"
      hash_key        = { name = "solution_owner_form_id", type = "S" }
      range_key       = { name = "sort_order", type = "N" }
      projection_type = "ALL"
    },
  ]
}

module "form_instance_assignments" {
  source   = "../ddb_app_data"
  solution = var.solution
  purpose  = "arb-form-instance-assignments"

  hash_key = { name = "id", type = "S" }

  global_secondary_indexes = [
    {
      name            = "assignee-open"
      hash_key        = { name = "assignee_user_id", type = "S" }
      range_key       = { name = "status", type = "S" }
      projection_type = "ALL"
    },
    {
      name            = "form-assignments"
      hash_key        = { name = "solution_owner_form_id", type = "S" }
      projection_type = "ALL"
    },
  ]
}

module "solution_collaborator_groups" {
  source   = "../ddb_app_data"
  solution = var.solution
  purpose  = "arb-solution-collaborator-groups"

  hash_key = { name = "id", type = "S" }

  global_secondary_indexes = [
    {
      name            = "solution-groups"
      hash_key        = { name = "registered_solution_id", type = "S" }
      projection_type = "ALL"
    },
  ]
}

module "solution_collaborator_group_members" {
  source   = "../ddb_app_data"
  solution = var.solution
  purpose  = "arb-solution-collaborator-group-members"

  hash_key  = { name = "group_id", type = "S" }
  range_key = { name = "user_id", type = "S" }
}

module "form_response_audit" {
  source   = "../ddb_app_data"
  solution = var.solution
  purpose  = "arb-form-response-audit"

  hash_key  = { name = "registered_solution_id", type = "S" }
  range_key = { name = "event_id", type = "S" }
}

module "user_solution_activity_watermark" {
  source   = "../ddb_app_data"
  solution = var.solution
  purpose  = "arb-user-solution-activity-watermark"

  hash_key  = { name = "user_id", type = "S" }
  range_key = { name = "registered_solution_id", type = "S" }
}

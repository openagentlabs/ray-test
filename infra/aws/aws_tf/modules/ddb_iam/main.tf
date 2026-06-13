###############################################################################
# iam.svc DynamoDB — tables using the tf_lib/dynamodb template copy at
# ../ddb_app_data (PK `id` on each; GSIs for account→users, user→logins, invite codes).
# Table names flow to iam.svc via root outputs → app_config.toml.
###############################################################################

module "users" {
  # User profile items (no credentials — passwords live on login rows).
  source = "../ddb_app_data"

  solution = var.solution
  purpose  = "iam-users"

  hash_key = {
    name = "id"
    type = "S"
  }

  global_secondary_indexes = [
    {
      name            = "account-users"
      hash_key        = { name = "account_id", type = "S" }
      range_key       = { name = "id", type = "S" }
      projection_type = "ALL"
    },
  ]
}

module "user_types" {
  source = "../ddb_app_data"

  solution = var.solution
  purpose  = "iam-user-types"

  hash_key = {
    name = "id"
    type = "S"
  }
}

module "login_types" {
  source = "../ddb_app_data"

  solution = var.solution
  purpose  = "iam-login-types"

  hash_key = {
    name = "id"
    type = "S"
  }
}

module "logins" {
  # Login items may include a non-key string attribute `password` (see iam.proto).
  # DynamoDB is schemaless for non-key attributes; no GSI or key change is required.
  source = "../ddb_app_data"

  solution = var.solution
  purpose  = "iam-logins"

  hash_key = {
    name = "id"
    type = "S"
  }

  global_secondary_indexes = [
    {
      name            = "user-logins"
      hash_key        = { name = "user_id", type = "S" }
      range_key       = { name = "id", type = "S" }
      projection_type = "ALL"
    },
  ]
}

module "skill_lists" {
  source = "../ddb_app_data"

  solution = var.solution
  purpose  = "iam-skill-lists"

  hash_key = {
    name = "id"
    type = "S"
  }
}

module "skills" {
  source = "../ddb_app_data"

  solution = var.solution
  purpose  = "iam-skills"

  hash_key = {
    name = "id"
    type = "S"
  }
}

module "user_skills" {
  source = "../ddb_app_data"

  solution = var.solution
  purpose  = "iam-user-skills"

  hash_key = {
    name = "id"
    type = "S"
  }

  global_secondary_indexes = [
    {
      name            = "user-skills"
      hash_key        = { name = "user_id", type = "S" }
      range_key       = { name = "id", type = "S" }
      projection_type = "ALL"
    },
  ]
}

module "sessions" {
  # Authenticated user sessions created by SignIn. Schemaless non-key attributes:
  # user_id, login_id, expires_at, is_revoked, created_at, updated_at, deleted_at.
  source = "../ddb_app_data"

  solution = var.solution
  purpose  = "iam-sessions"

  hash_key = {
    name = "id"
    type = "S"
  }
}

module "invites" {
  # Sign-up invite codes (GSI ``invite-codes`` on ``code`` for lookup by string).
  source = "../ddb_app_data"

  solution = var.solution
  purpose  = "iam-invites"

  hash_key = {
    name = "id"
    type = "S"
  }

  global_secondary_indexes = [
    {
      name            = "invite-codes"
      hash_key        = { name = "code", type = "S" }
      projection_type = "ALL"
    },
  ]
}

module "deployment_admin" {
  # Local-dev / ``make reset-iam`` bootstrap credentials only — not users/logins.
  source = "../ddb_app_data"

  solution = var.solution
  purpose  = "iam-deployment-admin"

  hash_key = {
    name = "id"
    type = "S"
  }

  global_secondary_indexes = [
    {
      name            = "deployment-admin-email"
      hash_key        = { name = "email", type = "S" }
      projection_type = "ALL"
    },
  ]
}

# RBAC — roles, permissions, assignments (iam.svc).
module "roles" {
  source   = "../ddb_app_data"
  solution = var.solution
  purpose  = "iam-roles"

  hash_key = { name = "id", type = "S" }

  global_secondary_indexes = [
    {
      name            = "role-codes"
      hash_key        = { name = "code", type = "S" }
      projection_type = "ALL"
    },
  ]
}

module "permissions" {
  source   = "../ddb_app_data"
  solution = var.solution
  purpose  = "iam-permissions"

  hash_key = { name = "id", type = "S" }

  global_secondary_indexes = [
    {
      name            = "permission-codes"
      hash_key        = { name = "code", type = "S" }
      projection_type = "ALL"
    },
  ]
}

module "role_permissions" {
  source   = "../ddb_app_data"
  solution = var.solution
  purpose  = "iam-role-permissions"

  hash_key  = { name = "role_id", type = "S" }
  range_key = { name = "permission_id", type = "S" }
}

module "user_role_assignments" {
  source   = "../ddb_app_data"
  solution = var.solution
  purpose  = "iam-user-role-assignments"

  hash_key  = { name = "user_id", type = "S" }
  range_key = { name = "role_id", type = "S" }
}

module "service_permissions" {
  source   = "../ddb_app_data"
  solution = var.solution
  purpose  = "iam-service-permissions"

  hash_key  = { name = "service_code", type = "S" }
  range_key = { name = "permission_code", type = "S" }
}

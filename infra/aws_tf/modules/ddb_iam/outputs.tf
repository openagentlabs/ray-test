###############################################################################
# infra/aws_tf/modules/ddb_iam — table names and ARNs for iam.svc
###############################################################################

output "users_table_name" {
  description = "DynamoDB table for iam.svc users."
  value       = module.users.table_name
}

output "users_table_arn" {
  description = "ARN of the iam.svc users DynamoDB table."
  value       = module.users.table_arn
}

output "user_types_table_name" {
  description = "DynamoDB table for iam.svc user types."
  value       = module.user_types.table_name
}

output "user_types_table_arn" {
  description = "ARN of the iam.svc user types DynamoDB table."
  value       = module.user_types.table_arn
}

output "user_skills_table_name" {
  description = "DynamoDB table for iam.svc user ↔ skill links."
  value       = module.user_skills.table_name
}

output "user_skills_table_arn" {
  description = "ARN of the iam.svc user ↔ skill links DynamoDB table."
  value       = module.user_skills.table_arn
}

output "login_types_table_name" {
  description = "DynamoDB table for iam.svc login types."
  value       = module.login_types.table_name
}

output "login_types_table_arn" {
  description = "ARN of the iam.svc login types DynamoDB table."
  value       = module.login_types.table_arn
}

output "logins_table_name" {
  description = "DynamoDB table for iam.svc logins."
  value       = module.logins.table_name
}

output "logins_table_arn" {
  description = "ARN of the iam.svc logins DynamoDB table."
  value       = module.logins.table_arn
}

output "skill_lists_table_name" {
  description = "DynamoDB table for iam.svc skill lists."
  value       = module.skill_lists.table_name
}

output "skill_lists_table_arn" {
  description = "ARN of the iam.svc skill lists DynamoDB table."
  value       = module.skill_lists.table_arn
}

output "skills_table_name" {
  description = "DynamoDB table for iam.svc skill catalog."
  value       = module.skills.table_name
}

output "skills_table_arn" {
  description = "ARN of the iam.svc skill catalog DynamoDB table."
  value       = module.skills.table_arn
}

output "sessions_table_name" {
  description = "DynamoDB table for iam.svc authenticated user sessions."
  value       = module.sessions.table_name
}

output "sessions_table_arn" {
  description = "ARN of the iam.svc sessions DynamoDB table."
  value       = module.sessions.table_arn
}

output "invites_table_name" {
  description = "DynamoDB table for iam.svc sign-up invites."
  value       = module.invites.table_name
}

output "invites_table_arn" {
  description = "ARN of the iam.svc invites DynamoDB table."
  value       = module.invites.table_arn
}

output "deployment_admin_table_name" {
  description = "DynamoDB table for iam.svc deployment-admin bootstrap (reset-iam only)."
  value       = module.deployment_admin.table_name
}

output "deployment_admin_table_arn" {
  description = "ARN of the iam.svc deployment-admin DynamoDB table."
  value       = module.deployment_admin.table_arn
}

output "roles_table_arn" {
  description = "ARN of the iam.svc RBAC roles DynamoDB table."
  value       = module.roles.table_arn
}

output "permissions_table_arn" {
  description = "ARN of the iam.svc RBAC permissions DynamoDB table."
  value       = module.permissions.table_arn
}

output "role_permissions_table_arn" {
  description = "ARN of the iam.svc RBAC role-permissions DynamoDB table."
  value       = module.role_permissions.table_arn
}

output "user_role_assignments_table_arn" {
  description = "ARN of the iam.svc RBAC user-role-assignments DynamoDB table."
  value       = module.user_role_assignments.table_arn
}

output "service_permissions_table_arn" {
  description = "ARN of the iam.svc RBAC service-permissions DynamoDB table."
  value       = module.service_permissions.table_arn
}

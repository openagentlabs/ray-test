output "form_groups_table_name" {
  description = "Form group catalog table."
  value       = module.form_groups.table_name
}

output "form_groups_table_arn" {
  description = "ARN of the form group catalog table."
  value       = module.form_groups.table_arn
}

output "form_templates_table_name" {
  description = "Form template table."
  value       = module.form_templates.table_name
}

output "form_templates_table_arn" {
  description = "ARN of the form template table."
  value       = module.form_templates.table_arn
}

output "form_template_questions_table_name" {
  description = "Form template question table."
  value       = module.form_template_questions.table_name
}

output "form_template_questions_table_arn" {
  description = "ARN of the form template question table."
  value       = module.form_template_questions.table_arn
}

output "solution_owner_forms_table_name" {
  description = "Solution owner form instance table."
  value       = module.solution_owner_forms.table_name
}

output "solution_owner_forms_table_arn" {
  description = "ARN of the solution owner form instance table."
  value       = module.solution_owner_forms.table_arn
}

output "solution_owner_form_content_table_name" {
  description = "Solution owner form content instance table."
  value       = module.solution_owner_form_content.table_name
}

output "solution_owner_form_content_table_arn" {
  description = "ARN of the solution owner form content table."
  value       = module.solution_owner_form_content.table_arn
}

output "form_instance_assignments_table_name" {
  description = "Form assignment table."
  value       = module.form_instance_assignments.table_name
}

output "form_instance_assignments_table_arn" {
  description = "ARN of the form assignment table."
  value       = module.form_instance_assignments.table_arn
}

output "solution_collaborator_groups_table_name" {
  description = "Solution collaborator group table."
  value       = module.solution_collaborator_groups.table_name
}

output "solution_collaborator_groups_table_arn" {
  description = "ARN of the solution collaborator group table."
  value       = module.solution_collaborator_groups.table_arn
}

output "solution_collaborator_group_members_table_name" {
  description = "Solution collaborator group member table."
  value       = module.solution_collaborator_group_members.table_name
}

output "solution_collaborator_group_members_table_arn" {
  description = "ARN of the solution collaborator group member table."
  value       = module.solution_collaborator_group_members.table_arn
}

output "form_response_audit_table_name" {
  description = "Form response audit table."
  value       = module.form_response_audit.table_name
}

output "form_response_audit_table_arn" {
  description = "ARN of the form response audit table."
  value       = module.form_response_audit.table_arn
}

output "user_solution_activity_watermark_table_name" {
  description = "Per-user solution activity watermark table."
  value       = module.user_solution_activity_watermark.table_name
}

output "user_solution_activity_watermark_table_arn" {
  description = "ARN of the per-user solution activity watermark table."
  value       = module.user_solution_activity_watermark.table_arn
}

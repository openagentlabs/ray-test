output "docstore_registry_table_name" {
  description = "DynamoDB table for logical table registry (PK id)."
  value       = module.docstore_registry.table_name
}

output "docstore_registry_table_arn" {
  description = "ARN of the docstore registry table."
  value       = module.docstore_registry.table_arn
}

output "docstore_groups_table_name" {
  description = "DynamoDB table for table groups (PK id)."
  value       = module.docstore_groups.table_name
}

output "docstore_groups_table_arn" {
  description = "ARN of the docstore groups table."
  value       = module.docstore_groups.table_arn
}

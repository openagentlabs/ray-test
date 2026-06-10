###############################################################################
# infra/aws_tf/modules/ddb_requirements — outputs
###############################################################################

output "requirement_documents_table_name" {
  description = "DynamoDB table for requirement document metadata (PK id)."
  value       = module.requirement_documents.table_name
}

output "requirement_documents_table_arn" {
  description = "ARN of the requirement documents table."
  value       = module.requirement_documents.table_arn
}

output "requirement_document_rows_table_name" {
  description = "DynamoDB table for requirement document rows (PK document_id, SK row_id)."
  value       = module.requirement_document_rows.table_name
}

output "requirement_document_rows_table_arn" {
  description = "ARN of the requirement document rows table."
  value       = module.requirement_document_rows.table_arn
}

output "requirement_import_jobs_table_name" {
  description = "DynamoDB table for requirement import jobs (PK id)."
  value       = module.requirement_import_jobs.table_name
}

output "requirement_import_jobs_table_arn" {
  description = "ARN of the requirement import jobs table."
  value       = module.requirement_import_jobs.table_arn
}

###############################################################################
# infra/aws_tf/modules/ddb_storage_documents — outputs
###############################################################################

output "document_files_table_name" {
  description = "DynamoDB table for storage.svc document metadata (PK path, SK file_name)."
  value       = module.document_files.table_name
}

output "document_files_table_arn" {
  description = "ARN of the storage document files table."
  value       = module.document_files.table_arn
}

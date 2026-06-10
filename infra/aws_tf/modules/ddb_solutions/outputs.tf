###############################################################################
# infra/aws_tf/modules/ddb_solutions — outputs
###############################################################################

output "solutions_table_name" {
  description = "DynamoDB table for ARB solution records (PK id; GSI owner-solutions)."
  value       = module.solutions.table_name
}

output "solutions_table_arn" {
  description = "ARN of the ARB solutions table."
  value       = module.solutions.table_arn
}

output "solution_history_table_name" {
  description = "DynamoDB table for per-solution workflow / AI+human activity history."
  value       = module.solution_history.table_name
}

output "solution_history_table_arn" {
  description = "ARN of the ARB solution history table."
  value       = module.solution_history.table_arn
}

output "solution_documents_table_name" {
  description = "DynamoDB table for ARB solution documents (PK id; GSI solution-documents)."
  value       = module.solution_documents.table_name
}

output "solution_documents_table_arn" {
  description = "ARN of the ARB solution documents table."
  value       = module.solution_documents.table_arn
}

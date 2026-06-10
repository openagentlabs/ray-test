###############################################################################
# infra/tf_lib/dynamodb — outputs
###############################################################################

output "region" {
  description = "AWS region for this table (from `var.solution.region`); use for SDK endpoints and CLI `--region`."
  value       = var.solution.region
}

output "stream_arn" {
  description = "Stream ARN when streams are enabled; otherwise null."
  value       = var.stream_enabled ? aws_dynamodb_table.this.stream_arn : null
}

output "stream_label" {
  description = "Timestamp stream label when streams are enabled; otherwise null."
  value       = var.stream_enabled ? aws_dynamodb_table.this.stream_label : null
}

output "table_arn" {
  description = "ARN of the DynamoDB table."
  value       = aws_dynamodb_table.this.arn
}

output "table_id" {
  description = "Table name (same as `table_name` output)."
  value       = aws_dynamodb_table.this.id
}

output "table_name" {
  description = "Deployed table name derived from solution, purpose, and account id."
  value       = aws_dynamodb_table.this.name
}

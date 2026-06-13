###############################################################################
# infra/aws_tf/modules/ddb_collaboration — outputs
###############################################################################

output "resource_aliases_table_name" {
  description = "DynamoDB table for resource aliases (PK alias; GSI entity-aliases)."
  value       = module.resource_aliases.table_name
}

output "resource_aliases_table_arn" {
  description = "ARN of the resource aliases table."
  value       = module.resource_aliases.table_arn
}

output "discussion_threads_table_name" {
  description = "DynamoDB table for discussion threads (PK id; GSI context-threads)."
  value       = module.discussion_threads.table_name
}

output "discussion_threads_table_arn" {
  description = "ARN of the discussion threads table."
  value       = module.discussion_threads.table_arn
}

output "discussion_messages_table_name" {
  description = "DynamoDB table for discussion messages (PK thread_id, SK message_id)."
  value       = module.discussion_messages.table_name
}

output "discussion_messages_table_arn" {
  description = "ARN of the discussion messages table."
  value       = module.discussion_messages.table_arn
}

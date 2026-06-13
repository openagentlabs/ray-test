###############################################################################
# infra/aws_tf/modules/ddb_arch_diagram_jobs — outputs
###############################################################################

output "conversion_jobs_table_name" {
  description = "DynamoDB table for arch.diagram.agent.svc conversion jobs (PK id)."
  value       = module.conversion_jobs.table_name
}

output "conversion_jobs_table_arn" {
  description = "ARN of the arch diagram conversion jobs table."
  value       = module.conversion_jobs.table_arn
}

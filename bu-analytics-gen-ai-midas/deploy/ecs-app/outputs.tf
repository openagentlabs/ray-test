# Legacy ECS/OMF outputs - kept as comments; not active for MIDAS EKS deployment.
# output "ecs_service_name" { ... }
# output "ecs_cluster_name" { ... }
# output "ecs_task_definition_arn" { ... }
# output "sqs_queue_name" { ... }
# output "sqs_queue_url" { ... }
# output "omf_data_s3_bucket_name" { ... }
# output "omf_data_s3_bucket_arn" { ... }
# output "nlb_arn" { ... }
# output "nlb_dns_name" { ... }
# output "opensearch_serverless_*" { ... }

# -----------------------------------------------------------------------------
# Secrets Manager - application config secret (midas-{env}-{region}/app).
# Populated after terraform apply via deploy/scripts/ci/populate-secrets.sh.
# -----------------------------------------------------------------------------

output "secretsmanager_app_secret_arn" {
  description = "ARN of the MIDAS application Secrets Manager secret (midas-{env}-us-east-1/app)."
  value       = module.secretsmanager.app_secret_arn
}

output "secretsmanager_app_secret_name" {
  description = "Friendly name of the MIDAS application Secrets Manager secret."
  value       = module.secretsmanager.app_secret_name
}

output "midas_app_secret_kubernetes_managed_by_terraform" {
  description = "When true, helm-deploy-releases.sh should set SKIP_K8S_APP_SECRET_SYNC=true (see deploy/.ci/terraform-env.sh from Jenkins) to skip duplicate SM→K8s sync."
  value       = var.terraform_sync_app_secret_to_kubernetes
}

# -----------------------------------------------------------------------------
# S3 - test bucket created by module.s3.
# -----------------------------------------------------------------------------

output "s3_test_bucket_id" {
  description = "Name of the MIDAS S3 test bucket."
  value       = module.s3.test_bucket_id
}

output "s3_test_bucket_arn" {
  description = "ARN of the MIDAS S3 test bucket."
  value       = module.s3.test_bucket_arn
}

# -----------------------------------------------------------------------------
# Observability - backend application CloudWatch Log Group
# Read by helm-deploy-releases.sh to inject LOG_CLOUDWATCH_LOG_GROUP.
# -----------------------------------------------------------------------------

output "backend_application_log_group_name" {
  description = "CloudWatch Log Group name for the MIDAS backend application (/midas/<environment>/backend). Injected into the backend pod as LOG_CLOUDWATCH_LOG_GROUP via Helm."
  value       = module.observability_app_logs.backend_application_log_group_name
}

output "backend_application_log_group_arn" {
  description = "CloudWatch Log Group ARN (reference for Fluent Bit / CW Agent IAM policies)."
  value       = module.observability_app_logs.backend_application_log_group_arn
}

# -----------------------------------------------------------------------------
# Observability - Phase B AMP outputs (only when observability_amp_enabled=true)
# Consumed by deploy/observability/otel-collector/values.yaml and Grafana setup.
# -----------------------------------------------------------------------------

output "amp_remote_write_url" {
  description = "AMP Remote Write URL for the ADOT Collector prometheusremotewrite exporter. Empty when observability_amp_enabled=false."
  value       = var.observability_amp_enabled ? module.observability_amp[0].amp_remote_write_url : ""
}

output "amp_query_endpoint" {
  description = "AMP query endpoint for the Grafana data source. Empty when observability_amp_enabled=false."
  value       = var.observability_amp_enabled ? module.observability_amp[0].amp_query_endpoint : ""
}

# -----------------------------------------------------------------------------
# Observability - Phase C OpenSearch outputs (only when observability_opensearch_enabled=true)
# -----------------------------------------------------------------------------

output "opensearch_domain_endpoint" {
  description = "OpenSearch domain VPC endpoint. Use in Fluent Bit opensearch output and OpenSearch Dashboards URL. Empty when observability_opensearch_enabled=false."
  value       = var.observability_opensearch_enabled ? module.observability_opensearch[0].opensearch_domain_endpoint : ""
}

output "opensearch_dashboards_url" {
  description = "OpenSearch Dashboards VPC-private URL. Empty when observability_opensearch_enabled=false."
  value       = var.observability_opensearch_enabled ? module.observability_opensearch[0].opensearch_dashboards_url : ""
}

# -----------------------------------------------------------------------------
# Observability - CloudWatch Container Insights (CloudWatch Agent DaemonSet)
# Empty strings when observability_cloudwatch_agent_enabled=false.
# -----------------------------------------------------------------------------

output "cloudwatch_agent_irsa_role_arn" {
  description = "IAM role ARN assumed by the cloudwatch-agent IRSA service account. Has AWS-managed CloudWatchAgentServerPolicy attached. Empty when observability_cloudwatch_agent_enabled=false."
  value       = var.observability_cloudwatch_agent_enabled ? module.observability_cloudwatch_agent[0].irsa_role_arn : ""
}

output "cloudwatch_agent_ecr_repository_url" {
  description = "Private ECR repository URL for the cloudwatch-agent image mirror. Empty when observability_cloudwatch_agent_enabled=false."
  value       = var.observability_cloudwatch_agent_enabled ? module.observability_cloudwatch_agent[0].ecr_repository_url_agent : ""
}

output "cloudwatch_agent_operator_ecr_repository_url" {
  description = "Private ECR repository URL for the cloudwatch-agent-operator image mirror. Empty when observability_cloudwatch_agent_enabled=false."
  value       = var.observability_cloudwatch_agent_enabled ? module.observability_cloudwatch_agent[0].ecr_repository_url_operator : ""
}

output "aws_account_id" {
  description = "AWS account ID targeted by this root module."
  value       = local.solution.account_id
}

output "aws_region" {
  description = "AWS region targeted by this root module."
  value       = local.solution.region
}

output "ddb_app_data_region" {
  description = "AWS region of the ddb_app_data DynamoDB table."
  value       = module.ddb_app_data.region
}

output "ddb_app_data_table_arn" {
  description = "ARN of the ddb_app_data DynamoDB table."
  value       = module.ddb_app_data.table_arn
}

output "ddb_app_data_table_name" {
  description = "Name of the ddb_app_data DynamoDB table."
  value       = module.ddb_app_data.table_name
}

output "ddb_iam_users_table_name" {
  description = "DynamoDB table for iam.svc users (PK id; GSI account-users on account_id, id)."
  value       = module.ddb_iam.users_table_name
}

output "ddb_iam_users_table_arn" {
  description = "ARN of the iam.svc users DynamoDB table."
  value       = module.ddb_iam.users_table_arn
}

output "ddb_iam_user_types_table_name" {
  description = "DynamoDB table for iam.svc user types."
  value       = module.ddb_iam.user_types_table_name
}

output "ddb_iam_user_types_table_arn" {
  description = "ARN of the iam.svc user types DynamoDB table."
  value       = module.ddb_iam.user_types_table_arn
}

output "ddb_iam_login_types_table_name" {
  description = "DynamoDB table for iam.svc login types."
  value       = module.ddb_iam.login_types_table_name
}

output "ddb_iam_login_types_table_arn" {
  description = "ARN of the iam.svc login types DynamoDB table."
  value       = module.ddb_iam.login_types_table_arn
}

output "ddb_iam_logins_table_name" {
  description = "DynamoDB table for iam.svc logins (PK id; GSI user-logins on user_id, id)."
  value       = module.ddb_iam.logins_table_name
}

output "ddb_iam_logins_table_arn" {
  description = "ARN of the iam.svc logins DynamoDB table."
  value       = module.ddb_iam.logins_table_arn
}

output "ddb_iam_skill_lists_table_name" {
  description = "DynamoDB table for iam.svc skill lists."
  value       = module.ddb_iam.skill_lists_table_name
}

output "ddb_iam_skill_lists_table_arn" {
  description = "ARN of the iam.svc skill lists DynamoDB table."
  value       = module.ddb_iam.skill_lists_table_arn
}

output "ddb_iam_skills_table_name" {
  description = "DynamoDB table for iam.svc skill catalog (PK id)."
  value       = module.ddb_iam.skills_table_name
}

output "ddb_iam_skills_table_arn" {
  description = "ARN of the iam.svc skill catalog DynamoDB table."
  value       = module.ddb_iam.skills_table_arn
}

output "ddb_iam_user_skills_table_name" {
  description = "DynamoDB table for iam.svc user ↔ skill links (PK id; GSI user-skills on user_id, id)."
  value       = module.ddb_iam.user_skills_table_name
}

output "ddb_iam_user_skills_table_arn" {
  description = "ARN of the iam.svc user ↔ skill links DynamoDB table."
  value       = module.ddb_iam.user_skills_table_arn
}

output "ddb_iam_sessions_table_name" {
  description = "DynamoDB table for iam.svc authenticated user sessions."
  value       = module.ddb_iam.sessions_table_name
}

output "ddb_iam_sessions_table_arn" {
  description = "ARN of the iam.svc sessions DynamoDB table."
  value       = module.ddb_iam.sessions_table_arn
}

output "ddb_iam_invites_table_name" {
  description = "DynamoDB table for iam.svc sign-up invites."
  value       = module.ddb_iam.invites_table_name
}

output "ddb_iam_invites_table_arn" {
  description = "ARN of the iam.svc invites DynamoDB table."
  value       = module.ddb_iam.invites_table_arn
}

output "ddb_iam_deployment_admin_table_name" {
  description = "DynamoDB table for iam.svc deployment-admin bootstrap (reset-iam)."
  value       = module.ddb_iam.deployment_admin_table_name
}

output "ddb_iam_deployment_admin_table_arn" {
  description = "ARN of the iam.svc deployment-admin DynamoDB table."
  value       = module.ddb_iam.deployment_admin_table_arn
}

output "ddb_solutions_table_name" {
  description = "DynamoDB table for ARB solution owner solution records."
  value       = module.ddb_solutions.solutions_table_name
}

output "ddb_solutions_table_arn" {
  description = "ARN of the ARB solutions DynamoDB table."
  value       = module.ddb_solutions.solutions_table_arn
}

output "ddb_solution_history_table_name" {
  description = "DynamoDB table for ARB solution workflow / activity history."
  value       = module.ddb_solutions.solution_history_table_name
}

output "ddb_solution_history_table_arn" {
  description = "ARN of the ARB solution history DynamoDB table."
  value       = module.ddb_solutions.solution_history_table_arn
}

output "ddb_solution_documents_table_name" {
  description = "DynamoDB table for ARB solution documents linked to solutions and storage paths."
  value       = module.ddb_solutions.solution_documents_table_name
}

output "ddb_solution_documents_table_arn" {
  description = "ARN of the ARB solution documents DynamoDB table."
  value       = module.ddb_solutions.solution_documents_table_arn
}

output "ddb_forms_form_groups_table_name" {
  description = "DynamoDB table for ARB form groups (solutions.svc catalog)."
  value       = module.ddb_forms.form_groups_table_name
}

output "ddb_forms_form_groups_table_arn" {
  description = "ARN of the ARB form groups table."
  value       = module.ddb_forms.form_groups_table_arn
}

output "ddb_forms_form_templates_table_name" {
  description = "DynamoDB table for ARB form templates."
  value       = module.ddb_forms.form_templates_table_name
}

output "ddb_forms_form_templates_table_arn" {
  description = "ARN of the ARB form templates table."
  value       = module.ddb_forms.form_templates_table_arn
}

output "ddb_forms_form_template_questions_table_name" {
  description = "DynamoDB table for ARB form template questions (framework controls CSV import)."
  value       = module.ddb_forms.form_template_questions_table_name
}

output "ddb_forms_form_template_questions_table_arn" {
  description = "ARN of the ARB form template questions table."
  value       = module.ddb_forms.form_template_questions_table_arn
}

output "ddb_forms_solution_owner_forms_table_name" {
  description = "DynamoDB table for solution-scoped form instances."
  value       = module.ddb_forms.solution_owner_forms_table_name
}

output "ddb_forms_solution_owner_forms_table_arn" {
  description = "ARN of the solution owner forms table."
  value       = module.ddb_forms.solution_owner_forms_table_arn
}

output "ddb_forms_solution_owner_form_content_table_name" {
  description = "DynamoDB table for per-question form content on solution forms."
  value       = module.ddb_forms.solution_owner_form_content_table_name
}

output "ddb_forms_solution_owner_form_content_table_arn" {
  description = "ARN of the solution owner form content table."
  value       = module.ddb_forms.solution_owner_form_content_table_arn
}

output "ddb_forms_form_instance_assignments_table_name" {
  description = "DynamoDB table for form instance user assignments."
  value       = module.ddb_forms.form_instance_assignments_table_name
}

output "ddb_forms_form_instance_assignments_table_arn" {
  description = "ARN of the form instance assignments table."
  value       = module.ddb_forms.form_instance_assignments_table_arn
}

output "ddb_forms_solution_collaborator_groups_table_name" {
  description = "DynamoDB table for solution collaborator groups (forms domain)."
  value       = module.ddb_forms.solution_collaborator_groups_table_name
}

output "ddb_forms_solution_collaborator_groups_table_arn" {
  description = "ARN of the solution collaborator groups table."
  value       = module.ddb_forms.solution_collaborator_groups_table_arn
}

output "ddb_forms_solution_collaborator_group_members_table_name" {
  description = "DynamoDB table for solution collaborator group membership."
  value       = module.ddb_forms.solution_collaborator_group_members_table_name
}

output "ddb_forms_solution_collaborator_group_members_table_arn" {
  description = "ARN of the solution collaborator group members table."
  value       = module.ddb_forms.solution_collaborator_group_members_table_arn
}

output "ddb_forms_form_response_audit_table_name" {
  description = "DynamoDB table for form response audit events."
  value       = module.ddb_forms.form_response_audit_table_name
}

output "ddb_forms_form_response_audit_table_arn" {
  description = "ARN of the form response audit table."
  value       = module.ddb_forms.form_response_audit_table_arn
}

output "ddb_forms_user_solution_activity_watermark_table_name" {
  description = "DynamoDB table for per-user solution activity watermarks."
  value       = module.ddb_forms.user_solution_activity_watermark_table_name
}

output "ddb_forms_user_solution_activity_watermark_table_arn" {
  description = "ARN of the user solution activity watermark table."
  value       = module.ddb_forms.user_solution_activity_watermark_table_arn
}

output "ddb_collaboration_resource_aliases_table_name" {
  description = "DynamoDB table for collaboration resource aliases (collaboration.svc)."
  value       = module.ddb_collaboration.resource_aliases_table_name
}

output "ddb_collaboration_resource_aliases_table_arn" {
  description = "ARN of the collaboration resource aliases table."
  value       = module.ddb_collaboration.resource_aliases_table_arn
}

output "ddb_collaboration_discussion_threads_table_name" {
  description = "DynamoDB table for collaboration discussion threads."
  value       = module.ddb_collaboration.discussion_threads_table_name
}

output "ddb_collaboration_discussion_threads_table_arn" {
  description = "ARN of the collaboration discussion threads table."
  value       = module.ddb_collaboration.discussion_threads_table_arn
}

output "ddb_collaboration_discussion_messages_table_name" {
  description = "DynamoDB table for collaboration discussion messages."
  value       = module.ddb_collaboration.discussion_messages_table_name
}

output "ddb_collaboration_discussion_messages_table_arn" {
  description = "ARN of the collaboration discussion messages table."
  value       = module.ddb_collaboration.discussion_messages_table_arn
}

output "iam_admin_role_arn" {
  description = "ARN of the arb-admin-role IAM role (AdministratorAccess; trust from this account root)."
  value       = module.iam_admin_role.role_arn
}

output "iam_admin_role_name" {
  description = "Name of the arb-admin-role IAM role."
  value       = module.iam_admin_role.role_name
}

output "iam_admin_role_unique_id" {
  description = "Unique id of the arb-admin-role IAM role."
  value       = module.iam_admin_role.unique_id
}

output "s3_exlservice_arb_general_bucket_arn" {
  description = "ARN of the storage.svc general S3 bucket (exlservice-arb-general)."
  value       = module.s3_exlservice_arb_general.bucket_arn
}

output "s3_exlservice_arb_general_bucket_name" {
  description = "Name of the storage.svc general S3 bucket."
  value       = module.s3_exlservice_arb_general.bucket_name
}

output "s3_exlservice_arb_general_bucket_regional_domain_name" {
  description = "Regional virtual-hosted-style domain for the general storage bucket."
  value       = module.s3_exlservice_arb_general.bucket_regional_domain_name
}

output "s3_exlservice_arb_general_object_url_https_prefix" {
  description = "HTTPS URL prefix for objects in the general storage bucket (append a key)."
  value       = module.s3_exlservice_arb_general.object_url_https_prefix
}

output "solution_name" {
  description = "Solution slug bundled into default_tags and module inputs."
  value       = local.solution.name
}

output "arch_diagram_agent_bedrock_foundation_model_id" {
  description = "Bedrock Claude foundation model id wired into IAM for arch.diagram.agent.svc."
  value       = var.arch_diagram_agent_bedrock_foundation_model_id
}

output "arch_diagram_agent_bedrock_inference_profile_id" {
  description = "Bedrock Claude inference profile id wired into IAM for arch.diagram.agent.svc."
  value       = var.arch_diagram_agent_bedrock_inference_profile_id
}

output "arch_diagram_agent_bedrock_invoke_resource_arns" {
  description = "Bedrock resource ARNs granted on the arch diagram agent IAM role (Converse / InvokeModel)."
  value       = local.arch_diagram_agent_bedrock_invoke_arns
}

output "arch_diagram_agent_bedrock_runtime_endpoint" {
  description = <<-EOT
    Regional HTTPS endpoint for the Bedrock Runtime API (boto3 / AWS SDK). Same region as `aws_region`.
    arch.diagram.agent.svc calls Bedrock via Strands using IAM from output `iam_arch_diagram_agent_bedrock_role_arn`.
    Serverless foundation models are enabled by default in commercial regions; access is enforced via IAM.
  EOT
  value       = "https://bedrock-runtime.${local.solution.region}.amazonaws.com"
}

output "ddb_arch_diagram_conversion_jobs_table_arn" {
  description = "ARN of the arch.diagram.agent.svc conversion jobs DynamoDB table."
  value       = module.ddb_arch_diagram_jobs.conversion_jobs_table_arn
}

output "ddb_arch_diagram_conversion_jobs_table_name" {
  description = "DynamoDB table for arch.diagram.agent.svc conversion jobs (PK id)."
  value       = module.ddb_arch_diagram_jobs.conversion_jobs_table_name
}

output "ddb_docstore_registry_table_name" {
  description = "DynamoDB table for document-storage.svc logical table registry."
  value       = module.ddb_docstore.docstore_registry_table_name
}

output "ddb_docstore_groups_table_name" {
  description = "DynamoDB table for document-storage.svc table groups."
  value       = module.ddb_docstore.docstore_groups_table_name
}

output "docstore_attachments_bucket_name" {
  description = "S3 bucket for document-storage.svc attachments."
  value       = module.docstore_search.docstore_attachments_bucket_name
}

output "docstore_opensearch_collection_endpoint" {
  description = "OpenSearch Serverless endpoint for document-storage.svc vector search."
  value       = module.docstore_search.docstore_opensearch_collection_endpoint
}

output "iam_document_storage_svc_role_arn" {
  description = "ARN of the IAM role for document-storage.svc (DynamoDB, S3, Bedrock embeddings)."
  value       = module.iam_document_storage_svc.role_arn
}

output "iam_document_storage_svc_role_name" {
  description = "Name of the IAM role for document-storage.svc."
  value       = module.iam_document_storage_svc.role_name
}

output "document_storage_bedrock_embed_model_ids" {
  description = "Bedrock Titan embedding model ids wired into IAM for document-storage.svc."
  value       = var.document_storage_bedrock_embed_model_ids
}

output "iam_arch_diagram_agent_bedrock_role_arn" {
  description = "ARN of the IAM role granting Bedrock invoke for arch.diagram.agent.svc."
  value       = module.iam_arch_diagram_agent_bedrock.role_arn
}

output "iam_arch_diagram_agent_bedrock_role_name" {
  description = "Name of the IAM role granting Bedrock invoke for arch.diagram.agent.svc."
  value       = module.iam_arch_diagram_agent_bedrock.role_name
}

output "iam_general_ai_agent_bedrock_role_arn" {
  description = "ARN of the IAM role granting Bedrock invoke for general.ai.agent.svc."
  value       = module.iam_general_ai_agent_bedrock.role_arn
}

output "iam_general_ai_agent_bedrock_role_name" {
  description = "Name of the IAM role granting Bedrock invoke for general.ai.agent.svc."
  value       = module.iam_general_ai_agent_bedrock.role_name
}

output "general_ai_agent_bedrock_foundation_model_id" {
  description = "Bedrock foundation model id wired into IAM (mirror `app_config.toml` `[agent.bedrock].foundation_model_id`)."
  value       = var.general_ai_agent_bedrock_foundation_model_id
}

output "general_ai_agent_bedrock_inference_profile_id" {
  description = "Bedrock inference profile id wired into IAM (mirror `app_config.toml` `[agent.bedrock].inference_profile_id`)."
  value       = var.general_ai_agent_bedrock_inference_profile_id
}

output "notification_sns_topic_arn" {
  description = "SNS topic ARN for notification.svc — set `[sns].topic_arn` in notification.svc/server/app_config.toml."
  value       = module.sns_notifications.topic_arn
}

output "notification_sns_topic_name" {
  description = "SNS topic name for notification.svc."
  value       = module.sns_notifications.topic_name
}

output "notification_sns_region" {
  description = "AWS region hosting the notification SNS topic (same as `aws_region`)."
  value       = local.solution.region
}

output "notification_sns_email_subscription_arns" {
  description = "Per-email SNS subscription ARNs (pending until each recipient confirms the AWS subscription email)."
  value       = module.sns_notifications.email_subscription_arns
}

output "notification_sns_iam_policy_hint" {
  description = <<-EOT
    Attach an IAM policy to the principal whose access keys the notification service uses, granting
    `sns:Publish`, `sns:Subscribe`, `sns:ListSubscriptionsByTopic`, and `sns:GetSubscriptionAttributes`
    on `notification_sns_topic_arn` (and optionally `sns:GetTopicAttributes`). Do not commit access
    keys; use environment variables or a role assumed by the workload.
  EOT
  value = {
    topic_arn = module.sns_notifications.topic_arn
    actions = [
      "sns:Publish",
      "sns:Subscribe",
      "sns:ListSubscriptionsByTopic",
      "sns:GetSubscriptionAttributes",
    ]
  }
}

output "general_ai_agent_bedrock_invoke_resource_arns" {
  description = "Bedrock resource ARNs granted on the general AI agent IAM role (Converse / InvokeModel)."
  value       = local.general_ai_agent_bedrock_invoke_arns
}

output "general_ai_agent_bedrock_runtime_endpoint" {
  description = <<-EOT
    Regional HTTPS endpoint for the Bedrock Runtime API (boto3 / AWS SDK). Same region as `aws_region`.
    The Next.js app talks to `general.ai.agent.svc` over gRPC, not to this URL; set
    `GENERAL_AI_AGENT_BEDROCK_RUNTIME_URL` on the frontend host only if you want the test page to display it.
    Model access still requires IAM (output `iam_general_ai_agent_bedrock_role_arn`) plus Bedrock model access in the account.
  EOT
  value       = "https://bedrock-runtime.${local.solution.region}.amazonaws.com"
}

# --- CloudWatch application logs (OpenTelemetry → PutLogEvents) ---

output "cloudwatch_application_log_group_names" {
  description = "Per-service CloudWatch log group names (CLOUDWATCH_LOG_GROUP_NAME per workload)."
  value       = module.cloudwatch_application_logs.log_group_names_by_key
}

output "cloudwatch_application_log_group_arns" {
  description = "Per-service CloudWatch log group ARNs."
  value       = module.cloudwatch_application_logs.log_group_arns_by_key
}

output "application_cloudwatch_logs_put_policy_arn" {
  description = "IAM policy ARN: attach to roles assumed by apps/services that emit logs via PutLogEvents."
  value       = module.cloudwatch_application_logs.application_logs_put_policy_arn
}

output "application_cloudwatch_logs_put_policy_name" {
  description = "IAM policy name for application log delivery."
  value       = module.cloudwatch_application_logs.application_logs_put_policy_name
}

output "application_logging_service_identity" {
  description = "Stable service.id and OTEL_SERVICE_NAME defaults per workload (also in log group tags)."
  value       = module.cloudwatch_application_logs.service_identity_by_key
}

output "containers_ecr_repository_urls" {
  description = "ECR repository URLs when containers_eks_enabled is true."
  value       = var.containers_eks_enabled ? module.containers_stack[0].ecr_repository_urls : {}
}

output "containers_eks_cluster_name" {
  description = "EKS cluster name when containers_eks_enabled is true."
  value       = var.containers_eks_enabled ? module.workloads_infra[0].cluster_name : ""
}

output "containers_eks_cluster_endpoint" {
  description = "EKS API server endpoint when containers_eks_enabled is true."
  value       = var.containers_eks_enabled ? module.workloads_infra[0].cluster_endpoint : ""
}

output "containers_k8s_namespace" {
  description = "Kubernetes namespace for ARB workloads when EKS is enabled."
  value       = var.containers_eks_enabled ? module.workloads_infra[0].k8s_namespace : ""
}

output "containers_k8s_service_dns_names" {
  description = "In-cluster DNS names for workloads when EKS is enabled."
  value       = var.containers_eks_enabled ? module.containers_stack[0].k8s_service_dns_names : {}
}

output "containers_workload_deploy_specs" {
  description = "Helm deploy metadata per workload when EKS is enabled."
  value       = var.containers_eks_enabled ? module.containers_stack[0].workload_deploy_specs : {}
}

output "eks_cloudwatch_dashboard_name" {
  description = "CloudWatch dashboard name for EKS cluster metrics and logs."
  value       = var.containers_eks_enabled ? module.workloads_infra[0].eks_cloudwatch_dashboard_name : ""
}

output "eks_cloudwatch_dashboard_arn" {
  description = "CloudWatch dashboard ARN for EKS cluster metrics and logs."
  value       = var.containers_eks_enabled ? module.workloads_infra[0].eks_cloudwatch_dashboard_arn : ""
}

output "eks_containers_log_group_name" {
  description = "CloudWatch log group for Fargate container stdout/stderr."
  value       = var.containers_eks_enabled ? module.workloads_infra[0].eks_containers_log_group_name : ""
}

output "eks_control_plane_log_group_name" {
  description = "CloudWatch log group for EKS control plane logs."
  value       = var.containers_eks_enabled ? module.workloads_infra[0].control_plane_log_group_name : ""
}

output "eks_container_insights_log_group_names" {
  description = "Container Insights log groups for the EKS cluster."
  value       = var.containers_eks_enabled ? module.workloads_infra[0].container_insights_log_group_names : {}
}

output "application_logging_env_reference" {
  description = <<-EOT
    Reference environment for workloads that ship OpenTelemetry logs to CloudWatch via the AWS SDK (no sidecar).
    Keys: frontend, aspire (Next.js hosts), iam_svc, general_ai_agent_svc, solutions_svc, storage_svc,
    notification_svc, collaboration_svc, document_storage_svc, arch_diagram_agent_svc (Python gRPC).
    Set CLOUDWATCH_LOGS_ENABLED=true, CLOUDWATCH_LOGS_REGION, CLOUDWATCH_LOG_GROUP_NAME from cloudwatch_application_log_group_names,
    OTEL_SERVICE_NAME / SERVICE_ID / OTEL_SERVICE_INSTANCE_ID from application_logging_service_identity (instance id unique per replica).
    Attach application_cloudwatch_logs_put_policy_arn to the workload IAM role.
    Regenerate repo defaults: npm run sync:terraform-outputs (or sync:cloudwatch-logging) from frontend/ or aspire.svc/.
  EOT
  value = {
    region                         = local.solution.region
    account_id                     = local.solution.account_id
    cloudwatch_logs_put_policy_arn = module.cloudwatch_application_logs.application_logs_put_policy_arn
    log_group_names                = module.cloudwatch_application_logs.log_group_names_by_key
    service_identity               = module.cloudwatch_application_logs.service_identity_by_key
  }
}

# Root module composition: call reusable modules from ./modules/ only.
# Human-oriented map of per-service AWS and Helm layout: ../deployed/aws/

module "ddb_app_data" {
  source = "./modules/ddb_app_data"

  solution = local.solution
  purpose  = "app-data"

  hash_key = {
    name = "id"
    type = "S"
  }
}

# IAM service (iam.svc) — DynamoDB from tf_lib template (modules/ddb_app_data)
# composed under modules/ddb_iam.

moved {
  from = module.ddb_iam_users
  to   = module.ddb_iam.module.users
}

moved {
  from = module.ddb_iam_user_types
  to   = module.ddb_iam.module.user_types
}

moved {
  from = module.ddb_iam_login_types
  to   = module.ddb_iam.module.login_types
}

moved {
  from = module.ddb_iam_logins
  to   = module.ddb_iam.module.logins
}

moved {
  from = module.ddb_iam_skill_lists
  to   = module.ddb_iam.module.skill_lists
}

module "ddb_iam" {
  source = "./modules/ddb_iam"

  solution = local.solution
}

# Solution owner workspace — DynamoDB (Next.js server actions read/write).
module "ddb_solutions" {
  source = "./modules/ddb_solutions"

  solution = local.solution
}

# ARB forms — templates, instances, assignments (solutions.svc).
module "ddb_forms" {
  source = "./modules/ddb_forms"

  solution = local.solution
}

# Collaboration — aliases, discussion threads (collaboration.svc).
module "ddb_collaboration" {
  source = "./modules/ddb_collaboration"

  solution = local.solution
}

# storage.svc — document file registry (path + file_name metadata).
module "ddb_storage_documents" {
  source = "./modules/ddb_storage_documents"

  solution = local.solution
}

# document-storage.svc — logical table registry and groups.
module "ddb_docstore" {
  source = "./modules/ddb_docstore"

  solution = local.solution
}

# arch.diagram.agent.svc — diagram conversion jobs (PK id; GSI jobs-by-status).
module "ddb_arch_diagram_jobs" {
  source = "./modules/ddb_arch_diagram_jobs"

  solution = local.solution
}

# Application-level logs (OpenTelemetry → AWS SDK PutLogEvents). Created before EKS
# observability wiring so Fargate / Container Insights can route into the same groups.
module "cloudwatch_application_logs" {
  source = "./modules/cloudwatch_application_logs"

  solution = local.solution

  retention_in_days = 30
}

# EKS Fargate cluster (must exist before IRSA-enabled IAM roles when containers_eks_enabled).
module "workloads_infra" {
  count  = var.containers_eks_enabled ? 1 : 0
  source = "./modules/workloads_infra"

  solution = local.solution

  application_log_group_arns       = [for arn in module.cloudwatch_application_logs.log_group_arns_by_key : arn]
  application_log_group_names      = module.cloudwatch_application_logs.log_group_names_by_key
  cloudwatch_log_retention_in_days = 30
  existing_vpc_id                  = var.containers_existing_vpc_id
  existing_subnet_ids              = var.containers_existing_subnet_ids

  providers = {
    kubernetes.eks = kubernetes.eks
  }
}

# document-storage.svc — IAM role (fixed name for OpenSearch principal wiring).
module "iam_document_storage_svc" {
  source = "./modules/iam_document_storage_svc"

  solution = local.solution

  role_name = "arb-document-storage-svc"

  irsa_trust = local.irsa_trust != null ? merge(local.irsa_trust, {
    service_account = "document-storage"
  }) : null

  docstore_registry_table_arn = module.ddb_docstore.docstore_registry_table_arn
  docstore_groups_table_arn   = module.ddb_docstore.docstore_groups_table_arn

  group_physical_table_arn_wildcard = local.docstore_group_physical_table_arn_wildcard

  attachments_bucket_arn = "arn:aws:s3:::${local.docstore_attachments_bucket}"

  bedrock_embed_resource_arns = local.document_storage_bedrock_embed_arns
}

# document-storage.svc — vector search (OpenSearch) and attachments S3.
module "docstore_search" {
  source = "./modules/docstore_search"

  solution = local.solution

  opensearch_principal_arns = [module.iam_document_storage_svc.role_arn]
}

# requirements.svc — legacy tables (retained until migration complete).
module "ddb_requirements" {
  source = "./modules/ddb_requirements"

  solution = local.solution
}

module "iam_admin_role" {
  source = "./modules/iam_admin_role"

  solution = local.solution
}

# General application storage (storage.svc) — private bucket; access via IAM / presigned URLs.
module "s3_exlservice_arb_general" {
  source = "./modules/s3_exlservice_arb_general"

  solution = local.solution
  purpose  = "exlservice-arb-general"

  bucket_name_override = "exlservice-arb-general"

  public_access_enabled = false
  force_destroy         = true
}

# general.ai.agent.svc — IAM role with Bedrock Runtime invoke for Anthropic (configurable via
# `general_ai_agent_bedrock_*` variables; keep in sync with `app_config.toml` `[agent.bedrock]`).
module "iam_general_ai_agent_bedrock" {
  source = "./modules/iam_general_ai_agent_bedrock"

  solution = local.solution

  role_name = "arb-general-ai-agent-bedrock"

  irsa_trust = local.irsa_trust != null ? merge(local.irsa_trust, {
    service_account = "general-ai-agent"
  }) : null

  bedrock_invoke_resource_arns = local.general_ai_agent_bedrock_invoke_arns
}

# arch.diagram.agent.svc — IAM role with Bedrock Runtime invoke (Claude Sonnet family).
module "iam_arch_diagram_agent_bedrock" {
  source = "./modules/iam_arch_diagram_agent_bedrock"

  solution = local.solution

  role_name = "arb-arch-diagram-agent-bedrock"

  irsa_trust = local.irsa_trust != null ? merge(local.irsa_trust, {
    service_account = "arch-diagram-agent"
  }) : null

  bedrock_invoke_resource_arns = local.arch_diagram_agent_bedrock_invoke_arns

  dynamodb_table_arns = [
    module.ddb_arch_diagram_jobs.conversion_jobs_table_arn,
  ]
}

# notification.svc — SNS topic for email notifications (publish from the gRPC service).
module "sns_notifications" {
  source = "./modules/sns_notifications"

  solution = local.solution

  email_subscription_endpoints = var.notification_sns_email_subscription_endpoints
}

check "general_ai_agent_bedrock_invoke_arns_nonempty" {
  assert {
    condition     = length(local.general_ai_agent_bedrock_invoke_arns) > 0
    error_message = "Set at least one of general_ai_agent_bedrock_foundation_model_id or general_ai_agent_bedrock_inference_profile_id (see infra/aws_tf/variables.tf)."
  }
}

check "arch_diagram_agent_bedrock_invoke_arns_nonempty" {
  assert {
    condition     = length(local.arch_diagram_agent_bedrock_invoke_arns) > 0
    error_message = "Set at least one of arch_diagram_agent_bedrock_foundation_model_id or arch_diagram_agent_bedrock_inference_profile_id (see infra/aws_tf/variables.tf)."
  }
}

check "document_storage_bedrock_embed_arns_nonempty" {
  assert {
    condition     = length(local.document_storage_bedrock_embed_arns) > 0
    error_message = "Set at least one document_storage_bedrock_embed_model_id (see infra/aws_tf/variables.tf)."
  }
}

# Container images (ECR), shared IRSA role, and EKS Fargate cluster — see infra/containers/README.md
module "containers_stack" {
  count  = var.containers_eks_enabled ? 1 : 0
  source = "./modules/containers_stack"

  solution = local.solution

  cluster_name      = module.workloads_infra[0].cluster_name
  namespace         = module.workloads_infra[0].k8s_namespace
  oidc_provider_arn = module.workloads_infra[0].oidc_provider_arn
  oidc_provider_url = module.workloads_infra[0].oidc_provider_url

  image_tag                                 = var.containers_image_tag
  application_logs_put_policy_arn           = module.cloudwatch_application_logs.application_logs_put_policy_arn
  bedrock_task_role_arn                     = module.iam_general_ai_agent_bedrock.role_arn
  bedrock_task_role_name                    = module.iam_general_ai_agent_bedrock.role_name
  arch_diagram_agent_bedrock_task_role_arn  = module.iam_arch_diagram_agent_bedrock.role_arn
  arch_diagram_agent_bedrock_task_role_name = module.iam_arch_diagram_agent_bedrock.role_name
  document_storage_task_role_arn            = module.iam_document_storage_svc.role_arn
  document_storage_task_role_name           = module.iam_document_storage_svc.role_name
  dynamodb_table_arns = concat(
    [
      module.ddb_iam.users_table_arn,
      module.ddb_iam.user_types_table_arn,
      module.ddb_iam.login_types_table_arn,
      module.ddb_iam.logins_table_arn,
      module.ddb_iam.skill_lists_table_arn,
      module.ddb_iam.skills_table_arn,
      module.ddb_iam.user_skills_table_arn,
      module.ddb_iam.sessions_table_arn,
      module.ddb_iam.invites_table_arn,
      module.ddb_iam.deployment_admin_table_arn,
      module.ddb_iam.roles_table_arn,
      module.ddb_iam.permissions_table_arn,
      module.ddb_iam.role_permissions_table_arn,
      module.ddb_iam.user_role_assignments_table_arn,
      module.ddb_iam.service_permissions_table_arn,
    ],
    [
      module.ddb_solutions.solutions_table_arn,
      module.ddb_solutions.solution_history_table_arn,
      module.ddb_solutions.solution_documents_table_arn,
    ],
    [
      module.ddb_forms.form_groups_table_arn,
      module.ddb_forms.form_templates_table_arn,
      module.ddb_forms.form_template_questions_table_arn,
      module.ddb_forms.solution_owner_forms_table_arn,
      module.ddb_forms.solution_owner_form_content_table_arn,
      module.ddb_forms.form_instance_assignments_table_arn,
      module.ddb_forms.solution_collaborator_groups_table_arn,
      module.ddb_forms.solution_collaborator_group_members_table_arn,
      module.ddb_forms.form_response_audit_table_arn,
      module.ddb_forms.user_solution_activity_watermark_table_arn,
    ],
    [
      module.ddb_collaboration.resource_aliases_table_arn,
      module.ddb_collaboration.discussion_threads_table_arn,
      module.ddb_collaboration.discussion_messages_table_arn,
    ],
    [
      module.ddb_storage_documents.document_files_table_arn,
    ],
    [
      module.ddb_docstore.docstore_registry_table_arn,
      module.ddb_docstore.docstore_groups_table_arn,
    ],
    [
      module.ddb_arch_diagram_jobs.conversion_jobs_table_arn,
    ],
    [
      module.ddb_requirements.requirement_documents_table_arn,
      module.ddb_requirements.requirement_document_rows_table_arn,
      module.ddb_requirements.requirement_import_jobs_table_arn,
    ],
  )
  s3_bucket_arns = [
    module.s3_exlservice_arb_general.bucket_arn,
  ]
  sns_topic_arn = module.sns_notifications.topic_arn

  workload_extra_environment = local.containers_workload_merged_environment
}

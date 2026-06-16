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

# Platform shared file bucket (S3 object store; mounted in EC2 pods via Mountpoint S3 CSI).
# Template: infra/tf_lib/s3_shared_files (hashicorp/aws aws_s3_bucket).
module "s3_shared_files" {
  count  = var.s3_shared_files_enabled ? 1 : 0
  source = "./modules/s3_shared_files"

  solution = local.solution
  purpose  = "shared-files"

  public_access_enabled = false
  versioning_enabled    = true
  force_destroy         = false

  additional_tags = {
    "s3:Purpose" = "shared-files"
    Component    = "shared-s3-files"
    Service      = "platform"
  }
}

# EKS Fargate cluster (must exist before IRSA-enabled IAM roles when containers_eks_enabled).
module "workloads_infra" {
  count  = var.containers_eks_enabled ? 1 : 0
  source = "./modules/workloads_infra"

  solution = local.solution

  cluster_name = local.containers_cluster_name_effective
  namespace    = local.containers_k8s_namespace_effective

  application_log_group_arns       = [for arn in module.cloudwatch_application_logs.log_group_arns_by_key : arn]
  application_log_group_names      = module.cloudwatch_application_logs.log_group_names_by_key
  cloudwatch_log_retention_in_days = 30
  existing_vpc_id                  = var.containers_existing_vpc_id
  existing_subnet_ids              = var.containers_existing_subnet_ids

  kuberay_enabled                   = var.kuberay_enabled
  kuberay_namespace                 = var.kuberay_namespace
  kuberay_operator_chart_version    = var.kuberay_operator_chart_version
  kuberay_ray_cluster_chart_version = var.kuberay_ray_cluster_chart_version
  ray_alb_ingress_group_name        = var.ray_alb_ingress_group_name
  ray_image_repository              = var.ray_image_repository
  ray_image_tag                     = var.ray_image_tag
  ray_node_count                    = var.ray_node_count
  ray_node_instance_type            = var.ray_node_instance_type
  ray_worker_max_replicas           = var.ray_worker_max_replicas
  ray_worker_min_replicas           = var.ray_worker_min_replicas

  fsx_lustre_enabled              = var.fsx_lustre_enabled
  fsx_lustre_storage_capacity_gib = var.fsx_lustre_storage_capacity_gib
  fsx_lustre_deployment_type      = var.fsx_lustre_deployment_type
  fsx_lustre_csi_chart_version    = var.fsx_lustre_csi_chart_version

  s3_shared_files_enabled           = var.s3_shared_files_enabled
  s3_shared_files_bucket_arn        = var.s3_shared_files_enabled ? module.s3_shared_files[0].bucket_arn : ""
  s3_shared_files_bucket_name       = var.s3_shared_files_enabled ? module.s3_shared_files[0].bucket_name : ""
  s3_shared_files_key_prefix        = var.s3_shared_files_key_prefix
  s3_shared_files_csi_addon_version = var.s3_shared_files_csi_addon_version

  fargate_workloads_namespace_enabled = var.containers_fargate_workloads_namespace_enabled

  providers = {
    kubernetes.eks = kubernetes.eks
    helm.eks       = helm.eks
  }
}

# document-storage.svc — IAM role (fixed name for OpenSearch principal wiring).
module "iam_document_storage_svc" {
  source = "./modules/iam_document_storage_svc"

  solution = local.solution

  role_name = local.iam_role_name.document_storage_svc

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

# storage.svc — platform files bucket (tf_lib/s3 template; distinct from legacy exlservice-arb-general).
module "s3_files" {
  source = "./modules/s3_files"

  solution = local.solution
  purpose  = "files"

  public_access_enabled = false
  versioning_enabled    = true
  force_destroy         = false

  additional_tags = {
    "s3:Purpose" = "files"
  }
}

# General application storage (storage.svc) — private bucket; access via IAM / presigned URLs.
module "s3_exlservice_arb_general" {
  source = "./modules/s3_exlservice_arb_general"

  solution = local.solution
  purpose  = "exlservice-arb-general"

  bucket_name_override  = "exlservice-arb-general"
  public_access_enabled = false
  force_destroy         = true
}

# general.ai.agent.svc — IAM role with Bedrock Runtime invoke for Anthropic (configurable via
# `general_ai_agent_bedrock_*` variables; keep in sync with `app_config.toml` `[agent.bedrock]`).
module "iam_general_ai_agent_bedrock" {
  source = "./modules/iam_general_ai_agent_bedrock"

  solution = local.solution

  role_name = local.iam_role_name.general_ai_agent

  irsa_trust = local.irsa_trust != null ? merge(local.irsa_trust, {
    service_account = "general-ai-agent"
  }) : null

  bedrock_invoke_resource_arns = local.general_ai_agent_bedrock_invoke_arns
}

# arch.diagram.agent.svc — IAM role with Bedrock Runtime invoke (Claude Sonnet family).
module "iam_arch_diagram_agent_bedrock" {
  source = "./modules/iam_arch_diagram_agent_bedrock"

  solution = local.solution

  role_name = local.iam_role_name.arch_diagram_agent

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

check "naming_no_double_hyphens" {
  assert {
    condition = length(trimspace(var.deployment_key_override)) > 0 || (
      !can(regex("--", local.deployment_key)) && !can(regex("--", local.solution_slug)) && !can(regex(
        "--",
        local.docstore_solution_slug,
      ))
    )
    error_message = "Physical names must use single hyphens only: deployment_key and composed slugs must not contain '--' (see constants.mdc). Set deployment_key_override only for legacy stacks."
  }
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

check "kuberay_requires_eks" {
  assert {
    condition     = !var.kuberay_enabled || var.containers_eks_enabled
    error_message = "Set containers_eks_enabled = true when kuberay_enabled is true."
  }
}

check "ray_compute_requires_feature_flag" {
  assert {
    condition     = var.containers_eks_enabled || !var.kuberay_enabled
    error_message = "KubeRay requires containers_eks_enabled = true."
  }
}

check "fsx_lustre_requires_eks" {
  assert {
    condition     = !var.fsx_lustre_enabled || var.containers_eks_enabled
    error_message = "Set containers_eks_enabled = true when fsx_lustre_enabled is true."
  }
}

check "fsx_lustre_requires_ec2_workloads" {
  assert {
    condition     = !var.fsx_lustre_enabled || var.kuberay_enabled
    error_message = "FSx Lustre mounts require EC2 nodes: enable kuberay_enabled when fsx_lustre_enabled is true."
  }
}

check "s3_shared_files_requires_eks" {
  assert {
    condition     = !var.s3_shared_files_enabled || var.containers_eks_enabled
    error_message = "Set containers_eks_enabled = true when s3_shared_files_enabled is true."
  }
}

check "s3_shared_files_requires_ec2_workloads" {
  assert {
    condition     = !var.s3_shared_files_enabled || var.kuberay_enabled
    error_message = "S3 shared file mounts require EC2 nodes: enable kuberay_enabled when s3_shared_files_enabled is true."
  }
}

check "shared_mounts_incompatible_with_fargate_workloads_namespace" {
  assert {
    condition = !var.containers_eks_enabled || (
      !var.fsx_lustre_enabled && !var.s3_shared_files_enabled
    ) || !var.containers_fargate_workloads_namespace_enabled
    error_message = "FSx/S3 CSI mounts cannot run on Fargate: set containers_fargate_workloads_namespace_enabled = false when fsx_lustre_enabled or s3_shared_files_enabled is true."
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
    module.s3_files.bucket_arn,
  ]
  sns_topic_arn = module.sns_notifications.topic_arn

  fsx_lustre_enabled        = var.fsx_lustre_enabled
  lustre_volume_name        = var.containers_eks_enabled && var.fsx_lustre_enabled ? module.workloads_infra[0].lustre_shared_volume_name : ""
  lustre_mount_path         = var.containers_eks_enabled && var.fsx_lustre_enabled ? module.workloads_infra[0].lustre_shared_mount_path : ""
  s3_shared_files_enabled   = var.s3_shared_files_enabled
  s3_shared_volume_name     = var.containers_eks_enabled && var.s3_shared_files_enabled ? module.workloads_infra[0].s3_shared_volume_name : ""
  s3_shared_mount_path      = var.containers_eks_enabled && var.s3_shared_files_enabled ? module.workloads_infra[0].s3_shared_mount_path : ""
  ray_node_pool_label_key   = var.containers_eks_enabled && var.kuberay_enabled ? module.workloads_infra[0].ray_node_pool_label_key : "ray.io/node-pool"
  ray_node_pool_label_value = var.containers_eks_enabled && var.kuberay_enabled ? module.workloads_infra[0].ray_node_pool_label_value : "ray"

  workloads = merge(
    {
      frontend               = { enabled = true }
      manager_web            = { enabled = true }
      iam_svc                = { enabled = true }
      general_ai_agent       = { enabled = true }
      solutions_svc          = { enabled = true }
      notification_svc       = { enabled = true }
      storage_svc            = { enabled = true }
      collaboration_svc      = { enabled = true }
      document_storage_svc   = { enabled = true }
      arch_diagram_agent_svc = { enabled = true }
    },
    var.containers_workloads,
  )

  workload_extra_environment = local.containers_workload_merged_environment
}

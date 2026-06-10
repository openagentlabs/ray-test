locals {
  solution = {
    name        = var.solution_name
    description = var.solution_description
    version     = var.solution_version
    date        = var.solution_date
    account_id  = var.aws_account_id
    region      = var.aws_region
  }

  docstore_solution_slug = lower(replace(local.solution.name, "_", "-"))

  docstore_attachments_bucket = "${local.docstore_solution_slug}-docstore-attachments-${local.solution.account_id}"

  docstore_group_physical_table_arn_wildcard = "arn:aws:dynamodb:${local.solution.region}:${local.solution.account_id}:table/${local.docstore_solution_slug}-docstore-grp-*"

  ecs_service_discovery_namespace = "arb-ai-assistant.local" # legacy; unused when EKS enabled

  k8s_namespace    = "arb-ai-assistant"
  k8s_dns_suffix   = "${local.k8s_namespace}.svc.cluster.local"
  k8s_service_host = "svc.cluster.local"

  document_storage_bedrock_embed_arns = [
    for model_id in var.document_storage_bedrock_embed_model_ids :
    "arn:aws:bedrock:${local.solution.region}::foundation-model/${model_id}"
    if length(trimspace(model_id)) > 0
  ]

  irsa_trust = var.containers_eks_enabled ? {
    oidc_provider_arn = module.workloads_infra[0].oidc_provider_arn
    oidc_provider_url = module.workloads_infra[0].oidc_provider_url
    namespace         = local.k8s_namespace
  } : null

  # Terraform-derived pod env (table names, buckets, OpenSearch endpoint, integration hosts).
  containers_workload_tf_environment = {
    document_storage_svc = {
      DOCUMENT_STORAGE_REGISTRY_DYNAMO_TABLE_NAME = module.ddb_docstore.docstore_registry_table_name
      DOCUMENT_STORAGE_GROUPS_DYNAMO_TABLE_NAME   = module.ddb_docstore.docstore_groups_table_name
      DOCUMENT_STORAGE_S3_BUCKET                  = module.docstore_search.docstore_attachments_bucket_name
      DOCUMENT_STORAGE_OPENSEARCH_ENDPOINT        = module.docstore_search.docstore_opensearch_collection_endpoint
    }
    arch_diagram_agent_svc = {
      ARCH_DIAGRAM_AGENT_CONVERSION_JOBS_DYNAMO_TABLE_NAME = module.ddb_arch_diagram_jobs.conversion_jobs_table_name
      ARCH_DIAGRAM_AGENT_DOCUMENT_STORAGE_ENABLED          = "true"
      ARCH_DIAGRAM_AGENT_DOCUMENT_STORAGE_GRPC_HOST        = "document-storage.${local.k8s_dns_suffix}"
      ARCH_DIAGRAM_AGENT_DOCUMENT_STORAGE_GRPC_PORT        = "8809"
      ARCH_DIAGRAM_AGENT_STORAGE_ENABLED                   = "true"
      ARCH_DIAGRAM_AGENT_STORAGE_GRPC_HOST                 = "storage.${local.k8s_dns_suffix}"
      ARCH_DIAGRAM_AGENT_STORAGE_GRPC_PORT                 = "8805"
    }
  }

  containers_workload_env_keys = toset(concat(
    keys(var.containers_workload_extra_environment),
    keys(var.containers_workload_secret_environment),
    keys(local.containers_workload_tf_environment),
  ))

  containers_workload_merged_environment = {
    for workload_key in local.containers_workload_env_keys :
    workload_key => merge(
      lookup(var.containers_workload_extra_environment, workload_key, {}),
      lookup(var.containers_workload_secret_environment, workload_key, {}),
      lookup(local.containers_workload_tf_environment, workload_key, {}),
    )
  }

  # Align with general.ai.agent.svc `app_config.toml` `[agent.bedrock]` and variables.tf
  # `general_ai_agent_bedrock_*` (foundation model + inference profile ARNs).

  general_ai_agent_bedrock_invoke_arns = concat(
    length(trimspace(var.general_ai_agent_bedrock_foundation_model_id)) > 0 ? [
      "arn:aws:bedrock:${local.solution.region}::foundation-model/${var.general_ai_agent_bedrock_foundation_model_id}"
    ] : [],
    length(trimspace(var.general_ai_agent_bedrock_inference_profile_id)) > 0 ? [
      "arn:aws:bedrock:${local.solution.region}:${local.solution.account_id}:inference-profile/${var.general_ai_agent_bedrock_inference_profile_id}"
    ] : [],
  )

  # Align with arch.diagram.agent.svc `app_config.toml` `[agent.bedrock]` and variables.tf
  # `arch_diagram_agent_bedrock_*` (Claude foundation model + inference profile ARNs).
  arch_diagram_agent_bedrock_invoke_arns = concat(
    length(trimspace(var.arch_diagram_agent_bedrock_foundation_model_id)) > 0 ? [
      "arn:aws:bedrock:${local.solution.region}::foundation-model/${var.arch_diagram_agent_bedrock_foundation_model_id}"
    ] : [],
    length(trimspace(var.arch_diagram_agent_bedrock_inference_profile_id)) > 0 ? [
      "arn:aws:bedrock:${local.solution.region}:${local.solution.account_id}:inference-profile/${var.arch_diagram_agent_bedrock_inference_profile_id}"
    ] : [],
  )
}

# THE ONLY FILE most engineers edit for this root. All other .tf files are locked structure.
# See `.cursor/rules/terrafrom.mdc` and `.cursor/rules/constants.mdc`.

solution_name        = "ray_test"
solution_description = "ARB - AI Assistant primary AWS infrastructure."
solution_version     = "0.1.0"
solution_date        = "2026-05-16"

# Deployment identity — see .cursor/rules/infras/resource-naming.mdc and resource-taging.mdc
deployment_environment = "dev"
deployment_index       = "0001"
deployment_instance    = "a1b2c3"
deployed_at            = "2026-06-11T12:00:00Z"
deployed_by            = "platform@example.com"
expires_at             = "2026-12-11T14:30:00Z"
resource_owner         = "platform@example.com"
owner_email            = "platform@example.com"
created_by             = "platform@example.com"
automation_ignore      = false
cost_code              = "CC-ARB-001"
department             = "Engineering"

aws_account_id = "017868795096"
aws_region     = "us-east-1"

# EKS + ECR (container deployment) — see infra/containers/README.md
containers_eks_enabled = true
containers_image_tag   = "latest"

# KubeRay + Ray EC2 node pool
kuberay_enabled = true

fsx_lustre_enabled      = true
s3_shared_files_enabled = true

# This workspace ships manager-web only; disable microservices without local source trees.
containers_workloads = {
  frontend               = { enabled = false }
  iam_svc                = { enabled = false }
  general_ai_agent       = { enabled = false }
  solutions_svc          = { enabled = false }
  notification_svc       = { enabled = false }
  storage_svc            = { enabled = false }
  collaboration_svc      = { enabled = false }
  document_storage_svc   = { enabled = false }
  arch_diagram_agent_svc = { enabled = false }
  manager_web            = { enabled = true }
}

# manager-web uses FSx/S3 CSI on Ray EC2 nodes — not compatible with Fargate profile.
containers_fargate_workloads_namespace_enabled = false

# Reuse prior ECS VPC when set; leave empty to create a new platform VPC (see vpc_platform).
# containers_existing_vpc_id = "vpc-xxxxxxxx"
# containers_existing_subnet_ids = ["subnet-xxxxxxxx", "subnet-yyyyyyyy"]

# Optional overrides (defaults match general.ai.agent.svc `app_config.toml` `[agent.bedrock]`):
# general_ai_agent_bedrock_foundation_model_id  = "anthropic.claude-sonnet-4-5-20250929-v1:0"
# general_ai_agent_bedrock_inference_profile_id = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"

# Optional overrides (defaults match arch.diagram.agent.svc `app_config.toml` `[agent.bedrock]`):
# arch_diagram_agent_bedrock_foundation_model_id  = "anthropic.claude-sonnet-4-5-20250929-v1:0"
# arch_diagram_agent_bedrock_inference_profile_id = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"

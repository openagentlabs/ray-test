# THE ONLY FILE most engineers edit for this root. All other .tf files are locked structure.
# See `.cursor/rules/terrafrom.mdc` and `.cursor/rules/constants.mdc`.

solution_name        = "ray_test"
solution_description = "Ray Test primary AWS infrastructure."
solution_version     = "0.1.0"
solution_date        = "2026-05-16"

# Deployment identity — see .cursor/rules/infras/resource-naming.mdc and resource-taging.mdc
deployment_environment = "dev"
deployment_index       = "0001"
deployment_instance    = "a1b2c3"
deployed_at            = "2026-06-11T12:00:00Z"
deployed_by            = "platform@example.com"
expires_at             = "2026-12-11T12:00:00Z" # use "" when no expiry (TAG_EMPTY)
resource_owner         = "platform@example.com"
owner_email            = "platform@example.com"
created_by             = "platform@example.com"
automation_ignore      = false
# resource_group_1     = "" # optional sub-grouping (TAG_EMPTY default)
# resource_group_2     = ""
# resource_group_3     = ""
cost_code              = "CC-ARB-001"
department             = "Engineering"
# cost_center          = "" # optional; defaults to cost_code

aws_account_id = "017868795096"
aws_region     = "us-east-1"

# EKS + ECR (container deployment) — see infra/containers/README.md
containers_eks_enabled = true
containers_image_tag   = "latest"

# KubeRay + Ray EC2 node pool — see infra/containers/README.md § KubeRay
kuberay_enabled = true

# Shared FSx Lustre + Mountpoint S3 mounts for manager-web (and Ray) on EC2 nodes
fsx_lustre_enabled      = true
s3_shared_files_enabled = true

# CSI mounts require EC2 (Ray node pool); Fargate profile on workloads namespace must stay off.
containers_fargate_workloads_namespace_enabled = false

# Optional overrides (defaults match general.ai.agent.svc `app_config.toml` `[agent.bedrock]`):
# general_ai_agent_bedrock_foundation_model_id  = "anthropic.claude-sonnet-4-5-20250929-v1:0"
# general_ai_agent_bedrock_inference_profile_id = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"

# Optional overrides (defaults match arch.diagram.agent.svc `app_config.toml` `[agent.bedrock]`):
# arch_diagram_agent_bedrock_foundation_model_id  = "anthropic.claude-sonnet-4-5-20250929-v1:0"
# arch_diagram_agent_bedrock_inference_profile_id = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"

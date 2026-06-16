# THE ONLY FILE most engineers edit for this root. All other .tf files are locked structure.
# See `.cursor/rules/terrafrom.mdc` and `.cursor/rules/constants/constants.mdc`.

solution_name        = "ray_test"
solution_description = "ARB - AI Assistant primary AWS infrastructure."
solution_version     = "0.1.0"
solution_date        = "2026-05-16"

aws_account_id = "017868795096"
aws_region     = "us-east-1"

# EKS + ECR (container deployment) — see infra/containers/README.md
containers_eks_enabled = true
containers_image_tag   = "latest"

# Optional overrides (defaults match general.ai.agent.svc `app_config.toml` `[agent.bedrock]`):
# general_ai_agent_bedrock_foundation_model_id  = "anthropic.claude-sonnet-4-5-20250929-v1:0"
# general_ai_agent_bedrock_inference_profile_id = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"

# Optional overrides (defaults match arch.diagram.agent.svc `app_config.toml` `[agent.bedrock]`):
# arch_diagram_agent_bedrock_foundation_model_id  = "anthropic.claude-sonnet-4-5-20250929-v1:0"
# arch_diagram_agent_bedrock_inference_profile_id = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"

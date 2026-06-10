# THE ONLY FILE most engineers edit for this root. All other .tf files are locked structure.
# See `.cursor/rules/terrafrom.mdc` and `.cursor/rules/constants.mdc`.

solution_name        = "arb_ai_assistant"
solution_description = "ARB - AI Assistant primary AWS infrastructure."
solution_version     = "0.1.0"
solution_date        = "2026-05-16"

aws_account_id = "017868795096"
aws_region     = "us-east-1"

# EKS + ECR (container deployment) — see infra/containers/README.md
containers_eks_enabled = true
containers_image_tag   = "latest"

# Reuse prior ECS VPC (account VPC quota is 5; do not create arb_ai_assistant-eks VPC).
containers_existing_vpc_id = "vpc-070c6351b94f95c59"
containers_existing_subnet_ids = [
  "subnet-06fe77dad078d6ede",
  "subnet-0c01428068aba265c",
]

# Optional overrides (defaults match general.ai.agent.svc `app_config.toml` `[agent.bedrock]`):
# general_ai_agent_bedrock_foundation_model_id  = "anthropic.claude-sonnet-4-5-20250929-v1:0"
# general_ai_agent_bedrock_inference_profile_id = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"

# Optional overrides (defaults match arch.diagram.agent.svc `app_config.toml` `[agent.bedrock]`):
# arch_diagram_agent_bedrock_foundation_model_id  = "anthropic.claude-sonnet-4-5-20250929-v1:0"
# arch_diagram_agent_bedrock_inference_profile_id = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"

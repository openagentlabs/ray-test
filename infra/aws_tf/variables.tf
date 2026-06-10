variable "aws_account_id" {
  description = "AWS account ID this stack deploys into. Must equal AWS_ACCOUNT_ID in .cursor/rules/constants.mdc."
  type        = string
  default     = "017868795096"
  nullable    = false
  validation {
    condition     = var.aws_account_id == "017868795096"
    error_message = "Account binding violated: this repo deploys only to the account in constants.mdc."
  }
}

variable "aws_region" {
  description = "AWS region this stack deploys into. Must equal AWS_DEFAULT_REGION in .cursor/rules/constants.mdc."
  type        = string
  default     = "us-east-1"
  nullable    = false
}

variable "solution_date" {
  description = "ISO-8601 (YYYY-MM-DD) release date of this version."
  type        = string
  nullable    = false
  validation {
    condition     = can(regex("^\\d{4}-\\d{2}-\\d{2}$", var.solution_date))
    error_message = "solution_date must be YYYY-MM-DD."
  }
}

variable "solution_description" {
  description = "Human-readable description of what this stack provisions."
  type        = string
  nullable    = false
}

variable "solution_name" {
  description = "Short slug for the solution (lower_snake_case)."
  type        = string
  nullable    = false
  validation {
    condition     = can(regex("^[a-z][a-z0-9_]*$", var.solution_name))
    error_message = "solution_name must be lower_snake_case starting with a letter."
  }
}

variable "solution_version" {
  description = "Semantic version (MAJOR.MINOR.PATCH) of this infrastructure release."
  type        = string
  nullable    = false
  validation {
    condition     = can(regex("^[0-9]+\\.[0-9]+\\.[0-9]+$", var.solution_version))
    error_message = "solution_version must be semver, e.g. 0.1.0."
  }
}

variable "general_ai_agent_bedrock_foundation_model_id" {
  description = <<-EOT
    Bedrock foundation model id (no ARN prefix), e.g. anthropic.claude-sonnet-4-5-20250929-v1:0.
    IAM allows bedrock:Converse / InvokeModel on
    arn:aws:bedrock:<aws_region>::foundation-model/<id>.
    Set to "" to omit that ARN from the policy. Must match general.ai.agent.svc `app_config.toml`
    `[agent.bedrock].foundation_model_id`.
  EOT
  type        = string
  nullable    = false
  default     = "anthropic.claude-sonnet-4-5-20250929-v1:0"
}

variable "notification_sns_email_subscription_endpoints" {
  description = <<-EOT
    Optional list of email addresses to subscribe to the notification SNS topic (protocol `email`).
    Recipients must confirm via AWS email before notification.svc publishes reach them.
  EOT
  type        = list(string)
  nullable    = false
  default     = []
}

variable "containers_eks_enabled" {
  description = <<-EOT
    When true, provision EKS (Fargate-only), ECR repositories, and IRSA roles for ARB workloads.
    Deploy pods with Helm via `make run-aws`. Push images with `make push-app-aws`.
  EOT
  type        = bool
  default     = false
  nullable    = false
}

variable "containers_image_tag" {
  description = "Default container image tag for Kubernetes Deployments."
  type        = string
  default     = "latest"
  nullable    = false
}

variable "containers_workload_extra_environment" {
  description = <<-EOT
    Committed per-APP_ENV static pod environment (APP_ENV, APP_TARGET, gRPC hosts).
  See `infra/envs/<env>/k8s.tfvars`. Not modified by deploy scripts.
  EOT
  type        = map(map(string))
  default     = {}
  nullable    = false
}

variable "containers_workload_secret_environment" {
  description = <<-EOT
    Gitignored secrets from `make/scaffold_secrets.py` (`infra/envs/<env>/secrets.auto.tfvars`).
  Merged with containers_workload_extra_environment at apply time.
  EOT
  type        = map(map(string))
  default     = {}
  nullable    = false
}

variable "containers_existing_vpc_id" {
  description = "Reuse an existing VPC for EKS instead of creating a new one (avoids VPC quota errors)."
  type        = string
  default     = ""
  nullable    = false
}

variable "containers_existing_subnet_ids" {
  description = "Public subnet IDs in containers_existing_vpc_id for EKS Fargate (minimum two AZs)."
  type        = list(string)
  default     = []
  nullable    = false
}

variable "general_ai_agent_bedrock_inference_profile_id" {
  description = <<-EOT
    Bedrock application inference profile id, e.g. us.anthropic.claude-sonnet-4-5-20250929-v1:0.
    IAM allows converse on
    arn:aws:bedrock:<aws_region>:<aws_account_id>:inference-profile/<id>.
    Set to "" to omit that ARN. Must match `app_config.toml` `[agent.bedrock].inference_profile_id`
    (and usually `[agent.bedrock].strands_model_id`).
  EOT
  type        = string
  nullable    = false
  default     = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"
}

variable "arch_diagram_agent_bedrock_foundation_model_id" {
  description = <<-EOT
    Bedrock Claude foundation model id for arch.diagram.agent.svc (no ARN prefix).
    IAM allows bedrock:Converse / InvokeModel on
    arn:aws:bedrock:<aws_region>::foundation-model/<id>.
    Must match arch.diagram.agent.svc `app_config.toml` `[agent.bedrock].foundation_model_id`.
  EOT
  type        = string
  nullable    = false
  default     = "anthropic.claude-sonnet-4-5-20250929-v1:0"
}

variable "document_storage_bedrock_embed_model_ids" {
  description = <<-EOT
    Bedrock Titan embedding model ids for document-storage.svc vector search.
    IAM allows bedrock:InvokeModel on arn:aws:bedrock:<aws_region>::foundation-model/<id>.
    Must match `app_config.toml` `[opensearch].bedrock_model_id` and image embed usage in code.
  EOT
  type        = list(string)
  nullable    = false
  default = [
    "amazon.titan-embed-text-v2:0",
    "amazon.titan-embed-image-v1:0",
  ]
}

variable "arch_diagram_agent_bedrock_inference_profile_id" {
  description = <<-EOT
    Bedrock Claude inference profile id for arch.diagram.agent.svc.
    IAM allows converse on
    arn:aws:bedrock:<aws_region>:<aws_account_id>:inference-profile/<id>.
    Must match `app_config.toml` `[agent.bedrock].inference_profile_id`
    (and usually `[agent.bedrock].strands_model_id`).
  EOT
  type        = string
  nullable    = false
  default     = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"
}

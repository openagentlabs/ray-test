###############################################################################
# IAM role for arch.diagram.agent.svc — Bedrock Runtime (Anthropic Claude Sonnet family)
###############################################################################

variable "solution" {
  description = <<-EOT
    Solution-wide metadata propagated from the root module (same shape as other child modules).
  EOT
  type = object({
    name                   = string
    description            = string
    version                = string
    date                   = string
    account_id             = string
    region                 = string
    deployment_environment = string
    deployment_index       = string
    deployment_instance    = string
    deployment_key         = string
    deployed_at            = string
    deployed_by            = string
    expires_at             = string
    cost_code              = string
    department             = string
  })
  nullable = false
}

variable "role_name" {
  description = "IAM role name for the Bedrock-scoped runtime role (unique in the account)."
  type        = string
  nullable    = false
}

variable "bedrock_invoke_resource_arns" {
  description = <<-EOT
    Resource ARNs for bedrock:Converse / InvokeModel (foundation models and/or inference profiles).
    Built from root `arch_diagram_agent_bedrock_foundation_model_id` and
    `arch_diagram_agent_bedrock_inference_profile_id`; must align with arch.diagram.agent.svc
    `app_config.toml` `[agent.bedrock]` (region + ids).
  EOT
  type        = list(string)
  nullable    = false
}

variable "dynamodb_table_arns" {
  description = "DynamoDB table ARNs for arch.diagram.agent.svc conversion jobs."
  type        = list(string)
  default     = []
  nullable    = false
}

variable "irsa_trust" {
  description = "EKS IRSA trust for this role's ServiceAccount (null when EKS is disabled)."
  type = object({
    oidc_provider_arn = string
    oidc_provider_url = string
    namespace         = string
    service_account   = string
  })
  default = null
}

variable "application_logs_put_policy_arn" {
  description = "IAM policy ARN for CloudWatch application logs (attach to task roles)."
  type        = string
  nullable    = false
}

variable "bedrock_task_role_arn" {
  description = "Task role ARN for general.ai.agent Bedrock invoke."
  type        = string
  nullable    = false
}

variable "bedrock_task_role_name" {
  description = "IAM role name for general.ai.agent (for policy attachments)."
  type        = string
  nullable    = false
}

variable "arch_diagram_agent_bedrock_task_role_arn" {
  description = "Task role ARN for arch.diagram.agent.svc Bedrock invoke."
  type        = string
  nullable    = false
}

variable "arch_diagram_agent_bedrock_task_role_name" {
  description = "IAM role name for arch.diagram.agent.svc (for policy attachments)."
  type        = string
  nullable    = false
}

variable "document_storage_task_role_arn" {
  description = "Task role ARN for document-storage.svc (DynamoDB, S3, Bedrock embeddings)."
  type        = string
  default     = ""
  nullable    = false
}

variable "document_storage_task_role_name" {
  description = "IAM role name for document-storage.svc (for policy attachments)."
  type        = string
  default     = ""
  nullable    = false
}

variable "dynamodb_table_arns" {
  description = "DynamoDB table ARNs granted to the shared EKS IRSA role (IAM, solutions, forms, collaboration)."
  type        = list(string)
  default     = []
  nullable    = false
}

variable "s3_bucket_arns" {
  description = "S3 bucket ARNs granted to the shared EKS IRSA role (storage.svc general bucket, etc.)."
  type        = list(string)
  default     = []
  nullable    = false
}

variable "sns_topic_arn" {
  description = "SNS topic ARN for notification.svc publish."
  type        = string
  default     = ""
  nullable    = false
}

variable "cluster_name" {
  description = "EKS cluster name."
  type        = string
  default     = "arb-ai-assistant"
  nullable    = false
}

variable "namespace" {
  description = "Kubernetes namespace for ARB workloads."
  type        = string
  default     = "arb-ai-assistant"
  nullable    = false
}

variable "oidc_provider_arn" {
  description = "IAM OIDC provider ARN from workloads_infra (IRSA trust)."
  type        = string
  nullable    = false
}

variable "oidc_provider_url" {
  description = "OIDC issuer host without https:// (IRSA trust)."
  type        = string
  nullable    = false
}

variable "image_tag" {
  description = "Container image tag pushed to each ECR repository."
  type        = string
  default     = "latest"
  nullable    = false
}

variable "solution" {
  description = "Solution-wide metadata propagated from the root module."
  type = object({
    name        = string
    description = string
    version     = string
    date        = string
    account_id  = string
    region      = string
  })
  nullable = false
}

variable "vpc_cidr" {
  description = "CIDR for the dedicated EKS Fargate VPC (created when containers stack is enabled)."
  type        = string
  default     = "10.42.0.0/16"
  nullable    = false
}

variable "workload_extra_environment" {
  description = <<-EOT
    Per-workload container environment variables merged into Kubernetes Deployments.
  Populated from `infra/envs/<env>/k8s.tfvars` and gitignored secrets. Keys must match workload_catalog keys.
  EOT
  type        = map(map(string))
  default     = {}
  nullable    = false
}

variable "workloads" {
  description = <<-EOT
    Workloads to deploy on EKS Fargate. Keys must match entries in local.workload_catalog.
    Override image_tag per workload via optional `image_tag` field.
  EOT
  type = map(object({
    enabled   = optional(bool, true)
    image_tag = optional(string)
  }))
  default = {
    frontend               = { enabled = true }
    iam_svc                = { enabled = true }
    general_ai_agent       = { enabled = true }
    solutions_svc          = { enabled = true }
    notification_svc       = { enabled = true }
    storage_svc            = { enabled = true }
    collaboration_svc      = { enabled = true }
    document_storage_svc   = { enabled = true }
    arch_diagram_agent_svc = { enabled = true }
  }
  nullable = false
}

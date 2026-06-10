###############################################################################
# IAM role for document-storage.svc — DynamoDB, S3 attachments, Bedrock embeddings.
###############################################################################

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

variable "role_name" {
  description = "IAM role name for document-storage.svc (fixed for OpenSearch principal wiring)."
  type        = string
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

variable "docstore_registry_table_arn" {
  description = "ARN of the docstore registry DynamoDB table."
  type        = string
  nullable    = false
}

variable "docstore_groups_table_arn" {
  description = "ARN of the docstore groups DynamoDB table."
  type        = string
  nullable    = false
}

variable "group_physical_table_arn_wildcard" {
  description = <<-EOT
    DynamoDB table ARN wildcard for runtime group physical tables
    (e.g. arn:aws:dynamodb:us-east-1:123:table/arb-ai-assistant-docstore-grp-*).
  EOT
  type        = string
  nullable    = false
}

variable "attachments_bucket_arn" {
  description = "ARN of the docstore attachments S3 bucket."
  type        = string
  nullable    = false
}

variable "bedrock_embed_resource_arns" {
  description = <<-EOT
    Bedrock foundation model ARNs for Titan text/image embeddings used by vector search.
    Built from root `document_storage_bedrock_embed_model_ids`.
  EOT
  type        = list(string)
  nullable    = false
}

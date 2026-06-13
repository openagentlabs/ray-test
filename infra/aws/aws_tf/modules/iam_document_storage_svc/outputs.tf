output "role_arn" {
  description = "ARN of the document-storage.svc IAM task role."
  value       = module.role.role_arn
}

output "role_name" {
  description = "IAM role name for document-storage.svc."
  value       = module.role.role_name
}

output "unique_id" {
  description = "IAM unique id for the role."
  value       = module.role.unique_id
}

output "data_plane_policy_name" {
  description = "Name of the inline IAM policy for DynamoDB, S3, and Bedrock."
  value       = aws_iam_role_policy.document_storage_data_plane.name
}

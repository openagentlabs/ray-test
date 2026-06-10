###############################################################################
# Forwarded from iam_role + inline policy name
###############################################################################

output "role_arn" {
  description = "ARN of the arch diagram agent Bedrock runtime IAM role."
  value       = module.role.role_arn
}

output "role_name" {
  description = "IAM role name for the Bedrock runtime role."
  value       = module.role.role_name
}

output "unique_id" {
  description = "IAM unique id for the role."
  value       = module.role.unique_id
}

output "bedrock_invoke_policy_name" {
  description = "Name of the inline IAM policy granting Bedrock invoke / converse."
  value       = aws_iam_role_policy.bedrock_invoke.name
}

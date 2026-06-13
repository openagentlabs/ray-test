output "role_arn" {
  description = "ARN of the deployer role"
  value       = aws_iam_role.deployer_role.arn
}

output "role_name" {
  description = "Name of the deployer role"
  value       = aws_iam_role.deployer_role.name
}

output "policy_arns" {
  description = "ARNs of the attached managed policies"
  value       = { for k, v in aws_iam_policy.deployer_policies : k => v.arn }
}

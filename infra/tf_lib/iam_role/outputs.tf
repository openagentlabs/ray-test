###############################################################################
# infra/tf_lib/iam_role — outputs callers typically wire to grants / CI
###############################################################################

output "assume_role_policy_json" {
  description = "Trust policy JSON applied to the role (echo of input; useful for documentation)."
  value       = var.assume_role_policy_json
}

output "managed_policy_arns" {
  description = "Managed policy ARNs attached to this role."
  value       = var.managed_policy_arns
}

output "role_arn" {
  description = "ARN of the IAM role (use in `Principal` or tool configuration)."
  value       = aws_iam_role.this.arn
}

output "role_id" {
  description = "Terraform resource id for the role (same as role name; distinct from `unique_id` and ARN)."
  value       = aws_iam_role.this.id
}

output "role_name" {
  description = "IAM role name (same as `var.role_name`)."
  value       = aws_iam_role.this.name
}

output "unique_id" {
  description = "IAM-generated unique id for the role (useful for some policy conditions)."
  value       = aws_iam_role.this.unique_id
}

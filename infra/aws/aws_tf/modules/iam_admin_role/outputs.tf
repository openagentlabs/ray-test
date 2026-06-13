###############################################################################
# infra/aws_tf/modules/iam_admin_role — outputs (forwarded from iam_role)
###############################################################################

output "assume_role_policy_json" {
  description = "Trust policy JSON applied to the administrator role."
  value       = module.role.assume_role_policy_json
}

output "managed_policy_arns" {
  description = "Managed policy ARNs attached to the administrator role."
  value       = module.role.managed_policy_arns
}

output "role_arn" {
  description = "ARN of the administrator IAM role."
  value       = module.role.role_arn
}

output "role_id" {
  description = "Stable IAM role id string for the administrator role."
  value       = module.role.role_id
}

output "role_name" {
  description = "IAM role name for the administrator role."
  value       = module.role.role_name
}

output "unique_id" {
  description = "IAM-generated unique id for the administrator role."
  value       = module.role.unique_id
}

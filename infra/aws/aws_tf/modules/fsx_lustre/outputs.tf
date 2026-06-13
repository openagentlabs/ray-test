output "file_system_arn" {
  description = "Amazon Resource Name of the FSx for Lustre file system."
  value       = try(aws_fsx_lustre_file_system.this[0].arn, null)
}

output "file_system_dns_name" {
  description = "DNS name for mounting the file system."
  value       = try(aws_fsx_lustre_file_system.this[0].dns_name, null)
}

output "file_system_id" {
  description = "Identifier of the file system (for example fs-12345678)."
  value       = try(aws_fsx_lustre_file_system.this[0].id, null)
}

output "file_system_mount_name" {
  description = "Lustre mount name used when mounting the file system."
  value       = try(aws_fsx_lustre_file_system.this[0].mount_name, null)
}

output "security_group_id" {
  description = "Security group attached to the FSx for Lustre file system."
  value       = try(aws_security_group.lustre[0].id, null)
}

output "storage_capacity_gib" {
  description = "Provisioned storage capacity in GiB."
  value       = var.storage_capacity
}

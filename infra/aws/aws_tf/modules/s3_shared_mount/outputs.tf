output "mount_path" {
  description = "Container mount path for the shared S3-backed volume."
  value       = local.mount_path
}

output "volume_name" {
  description = "Kubernetes volume name used in pod specs."
  value       = local.volume_name
}

output "pvc_names_by_namespace" {
  description = "Map of namespace to shared-s3-files PVC name."
  value       = { for ns, pvc in kubernetes_persistent_volume_claim.shared_s3_files : ns => pvc.metadata[0].name }
}

output "s3_csi_driver_service_account" {
  description = "kube-system service account used by the Mountpoint S3 EKS add-on (IRSA)."
  value       = local.service_account_name
}

output "s3_csi_driver_role_arn" {
  description = "IAM role ARN attached to the Mountpoint S3 CSI driver service account."
  value       = aws_iam_role.s3_csi.arn
}

output "bucket_key_prefix" {
  description = "Normalized S3 key prefix mounted into pods (always ends with /)."
  value       = local.normalized_bucket_key_prefix
}

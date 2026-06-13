output "mount_path" {
  description = "Container mount path for the shared Lustre volume."
  value       = local.mount_path
}

output "volume_name" {
  description = "Kubernetes volume name used in pod specs."
  value       = local.volume_name
}

output "pvc_names_by_namespace" {
  description = "Map of namespace to shared-lustre PVC name."
  value       = { for ns, pvc in kubernetes_persistent_volume_claim.shared_lustre : ns => pvc.metadata[0].name }
}

output "fsx_csi_controller_service_account" {
  description = "kube-system service account name for the FSx CSI controller (IRSA)."
  value       = local.service_account_name
}

output "fsx_csi_node_service_account" {
  description = "kube-system service account name for the FSx CSI node plugin."
  value       = "fsx-csi-node-sa"
}

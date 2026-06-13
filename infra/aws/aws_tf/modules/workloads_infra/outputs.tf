output "alb_controller_iam_role_arn" {
  description = "IAM role ARN for the AWS Load Balancer Controller (IRSA)."
  value       = module.eks_alb_controller.alb_controller_iam_role_arn
}

output "alb_ingress_class" {
  description = "IngressClass name for ALB-backed Ingress resources."
  value       = module.eks_alb_controller.ingress_class
}

output "alb_public_subnet_ids" {
  description = "Public subnet IDs for internet-facing Application Load Balancers."
  value       = module.vpc_platform.alb_public_subnet_ids
}

output "alb_security_group_id" {
  description = "Security group for internet-facing Application Load Balancers."
  value       = module.network_security_groups.alb_security_group_id
}

output "bastion_security_group_id" {
  description = "Security group for bastion hosts."
  value       = module.network_security_groups.bastion_security_group_id
}

output "bastion_subnet_ids" {
  description = "Private subnet IDs for bastion hosts."
  value       = module.vpc_platform.bastion_subnet_ids
}

output "cluster_arn" {
  description = "EKS cluster ARN."
  value       = module.eks_platform.cluster_arn
}

output "cluster_certificate_authority_data" {
  description = "Base64-encoded CA certificate for the EKS API."
  value       = module.eks_platform.cluster_certificate_authority_data
}

output "cluster_endpoint" {
  description = "EKS API server endpoint."
  value       = module.eks_platform.cluster_endpoint
}

output "cluster_name" {
  description = "EKS cluster name."
  value       = module.eks_platform.cluster_name
}

output "control_plane_log_group_name" {
  description = "CloudWatch log group for EKS control plane logs."
  value       = module.eks_platform.control_plane_log_group_name
}

output "eks_cloudwatch_dashboard_arn" {
  description = "CloudWatch dashboard ARN for EKS metrics and logs."
  value       = module.eks_cloudwatch.dashboard_arn
}

output "eks_cloudwatch_dashboard_name" {
  description = "CloudWatch dashboard name for EKS metrics and logs."
  value       = module.eks_cloudwatch.dashboard_name
}

output "eks_containers_log_group_name" {
  description = "CloudWatch log group for Fargate container stdout/stderr."
  value       = module.eks_cloudwatch.eks_containers_log_group_name
}

output "container_insights_log_group_names" {
  description = "Container Insights log groups for the EKS cluster."
  value       = module.eks_cloudwatch.container_insights_log_group_names
}

output "eks_workloads_security_group_id" {
  description = "Security group for EKS Fargate workload ENIs."
  value       = module.network_security_groups.eks_workloads_security_group_id
}

output "k8s_namespace" {
  description = "Kubernetes namespace for ARB workloads."
  value       = module.eks_platform.namespace
}

output "oidc_provider_arn" {
  description = "IAM OIDC provider ARN for IRSA."
  value       = module.eks_platform.oidc_provider_arn
}

output "oidc_provider_url" {
  description = "OIDC issuer host (without https://) for IRSA trust policies."
  value       = module.eks_platform.oidc_provider_url
}

output "subnet_ids" {
  description = "VPC subnet IDs used by the EKS cluster (ALB public + EKS private)."
  value       = module.vpc_platform.subnet_ids
}

output "vpc_cidr_block" {
  description = "CIDR block of the platform VPC."
  value       = module.vpc_platform.vpc_cidr_block
}

output "vpc_id" {
  description = "VPC ID hosting the EKS cluster."
  value       = module.vpc_platform.vpc_id
}

output "cluster_security_group_id" {
  description = "EKS-managed primary security group for the cluster and EC2 nodes."
  value       = module.eks_platform.cluster_security_group_id
}

output "ray_node_group_name" {
  description = "EKS managed node group name for Ray compute when KubeRay is enabled."
  value       = local.ray_compute_enabled ? module.eks_node_group[0].node_group_name : ""
}

output "ray_node_pool_label_key" {
  description = "Node label key for the Ray EC2 compute pool."
  value       = local.ray_compute_enabled ? module.eks_node_group[0].node_pool_label_key : var.ray_node_pool_label_key
}

output "ray_node_pool_label_value" {
  description = "Node label value for the Ray EC2 compute pool."
  value       = local.ray_compute_enabled ? module.eks_node_group[0].node_pool_label_value : var.ray_node_pool_label_value
}

output "kuberay_namespace" {
  description = "Kubernetes namespace for KubeRay when kuberay_enabled is true."
  value       = var.kuberay_enabled ? module.kuberay_operator[0].namespace : ""
}

output "ray_dashboard_url" {
  description = "HTTP URL for the Ray dashboard and Jobs API ALB (when provisioned)."
  value       = var.kuberay_enabled ? module.ray_cluster[0].ray_dashboard_url : ""
}

output "ray_metrics_url" {
  description = "HTTP URL for Ray head Prometheus metrics via ALB (when provisioned)."
  value       = var.kuberay_enabled ? module.ray_cluster[0].ray_metrics_url : ""
}

output "ray_alb_hostname" {
  description = "ALB DNS hostname for the Ray dashboard ingress."
  value       = var.kuberay_enabled ? module.ray_cluster[0].ray_alb_hostname : ""
}

output "fsx_lustre_file_system_dns_name" {
  description = "DNS name for mounting the shared FSx for Lustre file system."
  value       = var.fsx_lustre_enabled ? module.fsx_lustre[0].file_system_dns_name : ""
}

output "fsx_lustre_file_system_id" {
  description = "Identifier of the shared FSx for Lustre file system."
  value       = var.fsx_lustre_enabled ? module.fsx_lustre[0].file_system_id : ""
}

output "fsx_lustre_mount_name" {
  description = "Lustre mount name for the shared file system."
  value       = var.fsx_lustre_enabled ? module.fsx_lustre[0].file_system_mount_name : ""
}

output "lustre_shared_mount_path" {
  description = "Container mount path for the shared Lustre volume (/mnt/lustre)."
  value       = var.fsx_lustre_enabled ? module.lustre_shared_mount[0].mount_path : ""
}

output "lustre_shared_volume_name" {
  description = "Kubernetes volume name for the shared Lustre PVC (shared-lustre)."
  value       = var.fsx_lustre_enabled ? module.lustre_shared_mount[0].volume_name : ""
}

output "s3_shared_files_bucket_name" {
  description = "Name of the shared S3 bucket mounted into EC2 workloads."
  value       = var.s3_shared_files_enabled ? var.s3_shared_files_bucket_name : ""
}

output "s3_shared_mount_path" {
  description = "Container mount path for the shared S3-backed volume (/mnt/s3-files)."
  value       = var.s3_shared_files_enabled ? module.s3_shared_mount[0].mount_path : ""
}

output "s3_shared_volume_name" {
  description = "Kubernetes volume name for the shared S3 PVC (shared-s3-files)."
  value       = var.s3_shared_files_enabled ? module.s3_shared_mount[0].volume_name : ""
}

output "s3_csi_driver_role_arn" {
  description = "IAM role ARN for the Mountpoint S3 CSI driver (IRSA)."
  value       = var.s3_shared_files_enabled ? module.s3_shared_mount[0].s3_csi_driver_role_arn : ""
}

module "vpc_platform" {
  source = "../vpc_platform"

  solution                   = var.solution
  vpc_cidr                   = var.vpc_cidr
  cluster_name               = local.cluster_name
  existing_vpc_id            = var.existing_vpc_id
  existing_subnet_ids        = var.existing_subnet_ids
  single_nat_gateway_enabled = var.single_nat_gateway_enabled
  vpc_endpoints_enabled      = var.vpc_endpoints_enabled
}

module "network_security_groups" {
  source = "../network_security_groups"

  solution                 = var.solution
  vpc_id                   = module.vpc_platform.vpc_id
  vpc_cidr_block           = module.vpc_platform.vpc_cidr_block
  cluster_name             = local.cluster_name
  alb_ingress_cidr_blocks  = var.alb_ingress_cidr_blocks
  bastion_ssh_cidr_blocks  = var.bastion_ssh_cidr_blocks
  workload_container_ports = var.workload_container_ports
}

module "eks_platform" {
  source = "../eks_platform"

  solution              = var.solution
  cluster_name          = local.cluster_name
  namespace             = local.namespace
  vpc_id                = module.vpc_platform.vpc_id
  subnet_ids            = module.vpc_platform.subnet_ids
  fargate_subnet_ids    = module.vpc_platform.fargate_subnet_ids
  log_retention_in_days = var.cloudwatch_log_retention_in_days
  cluster_security_group_ids = [
    module.network_security_groups.eks_cluster_security_group_id,
    module.network_security_groups.eks_workloads_security_group_id,
  ]
  fargate_workloads_namespace_enabled = var.fargate_workloads_namespace_enabled
}

module "eks_cloudwatch" {
  source = "../eks_cloudwatch"

  providers = {
    kubernetes = kubernetes.eks
  }

  solution                        = var.solution
  cluster_name                    = module.eks_platform.cluster_name
  subnet_ids                      = module.vpc_platform.fargate_subnet_ids
  oidc_provider_arn               = module.eks_platform.oidc_provider_arn
  oidc_provider_url               = module.eks_platform.oidc_provider_url
  fargate_pod_execution_role_arn  = module.eks_platform.fargate_pod_execution_role_arn
  fargate_pod_execution_role_name = module.eks_platform.fargate_pod_execution_role_name
  application_log_group_arns      = var.application_log_group_arns
  application_log_group_names     = var.application_log_group_names
  retention_in_days               = var.cloudwatch_log_retention_in_days

  depends_on = [module.eks_platform]
}

module "eks_alb_controller" {
  source = "../eks_alb_controller"

  providers = {
    helm.eks = helm.eks
  }

  solution               = var.solution
  cluster_name           = module.eks_platform.cluster_name
  vpc_id                 = module.vpc_platform.vpc_id
  oidc_provider_arn      = module.eks_platform.oidc_provider_arn
  oidc_provider_url      = module.eks_platform.oidc_provider_url
  alb_ingress_group_name = var.alb_ingress_group_name
  chart_version          = var.alb_controller_chart_version

  depends_on = [
    module.eks_platform,
    module.vpc_platform,
  ]
}

module "eks_node_group" {
  count  = local.ray_compute_enabled ? 1 : 0
  source = "../eks_node_group"

  solution                           = var.solution
  cluster_name                       = module.eks_platform.cluster_name
  subnet_ids                         = var.fsx_lustre_enabled ? [module.vpc_platform.eks_private_subnet_ids[0]] : module.vpc_platform.eks_private_subnet_ids
  node_count                         = var.ray_node_count
  node_instance_type                 = var.ray_node_instance_type
  cluster_security_group_id          = module.eks_platform.cluster_security_group_id
  additional_security_group_ids      = [module.network_security_groups.eks_workloads_security_group_id]
  install_lustre_client              = var.fsx_lustre_enabled
  cluster_endpoint                   = module.eks_platform.cluster_endpoint
  cluster_certificate_authority_data = module.eks_platform.cluster_certificate_authority_data
  cluster_service_ipv4_cidr          = module.eks_platform.cluster_service_ipv4_cidr

  depends_on = [module.eks_platform]
}

module "fsx_lustre" {
  count  = var.fsx_lustre_enabled ? 1 : 0
  source = "../fsx_lustre"

  solution = var.solution
  purpose  = "shared-lustre"

  subnet_ids     = [module.vpc_platform.eks_private_subnet_ids[0]]
  vpc_cidr_block = module.vpc_platform.vpc_cidr_block
  workload_security_group_ids = [
    module.network_security_groups.eks_workloads_security_group_id,
    module.eks_platform.cluster_security_group_id,
  ]

  deployment_type  = var.fsx_lustre_deployment_type
  storage_capacity = var.fsx_lustre_storage_capacity_gib

  depends_on = [module.vpc_platform, module.network_security_groups, module.eks_platform]
}

module "kuberay_operator" {
  count  = var.kuberay_enabled ? 1 : 0
  source = "../kuberay_operator"

  providers = {
    helm.eks       = helm.eks
    kubernetes.eks = kubernetes.eks
  }

  solution              = var.solution
  chart_version         = var.kuberay_operator_chart_version
  namespace             = var.kuberay_namespace
  node_pool_label_key   = module.eks_node_group[0].node_pool_label_key
  node_pool_label_value = module.eks_node_group[0].node_pool_label_value

  depends_on = [
    module.eks_node_group,
    module.eks_alb_controller,
  ]
}

module "lustre_shared_mount" {
  count  = var.fsx_lustre_enabled ? 1 : 0
  source = "../lustre_shared_mount"

  providers = {
    helm.eks       = helm.eks
    kubernetes.eks = kubernetes.eks
  }

  solution               = var.solution
  cluster_name           = module.eks_platform.cluster_name
  oidc_provider_arn      = module.eks_platform.oidc_provider_arn
  oidc_provider_url      = module.eks_platform.oidc_provider_url
  chart_version          = var.fsx_lustre_csi_chart_version
  file_system_id         = module.fsx_lustre[0].file_system_id
  file_system_dns_name   = module.fsx_lustre[0].file_system_dns_name
  file_system_mount_name = module.fsx_lustre[0].file_system_mount_name
  storage_capacity_gib   = var.fsx_lustre_storage_capacity_gib
  mount_namespaces       = local.lustre_mount_namespaces
  node_pool_label_key    = module.eks_node_group[0].node_pool_label_key
  node_pool_label_value  = module.eks_node_group[0].node_pool_label_value

  depends_on = [
    module.fsx_lustre,
    module.eks_node_group,
    module.eks_alb_controller,
    kubernetes_namespace.workloads,
    module.kuberay_operator,
  ]
}

module "s3_shared_mount" {
  count  = var.s3_shared_files_enabled ? 1 : 0
  source = "../s3_shared_mount"

  providers = {
    kubernetes.eks = kubernetes.eks
  }

  solution          = var.solution
  cluster_name      = module.eks_platform.cluster_name
  oidc_provider_arn = module.eks_platform.oidc_provider_arn
  oidc_provider_url = module.eks_platform.oidc_provider_url
  addon_version     = var.s3_shared_files_csi_addon_version
  bucket_arn        = var.s3_shared_files_bucket_arn
  bucket_name       = var.s3_shared_files_bucket_name
  bucket_key_prefix = var.s3_shared_files_key_prefix
  mount_namespaces  = local.s3_mount_namespaces

  depends_on = [
    module.eks_platform,
    module.eks_node_group,
    module.eks_alb_controller,
    kubernetes_namespace.workloads,
    module.kuberay_operator,
  ]
}

module "ray_cluster" {
  count  = var.kuberay_enabled ? 1 : 0
  source = "../ray_cluster"

  providers = {
    helm.eks       = helm.eks
    kubernetes.eks = kubernetes.eks
  }

  solution                = var.solution
  namespace               = module.kuberay_operator[0].namespace
  chart_version           = var.kuberay_ray_cluster_chart_version
  ray_image_tag           = var.ray_image_tag
  ray_image_repository    = var.ray_image_repository
  ingress_class           = module.eks_alb_controller.ingress_class
  alb_ingress_group_name  = var.ray_alb_ingress_group_name
  node_pool_label_key     = module.eks_node_group[0].node_pool_label_key
  node_pool_label_value   = module.eks_node_group[0].node_pool_label_value
  worker_min_replicas     = var.ray_worker_min_replicas
  worker_max_replicas     = var.ray_worker_max_replicas
  lustre_mount_enabled    = var.fsx_lustre_enabled
  lustre_volume_name      = var.fsx_lustre_enabled ? module.lustre_shared_mount[0].volume_name : ""
  lustre_mount_path       = var.fsx_lustre_enabled ? module.lustre_shared_mount[0].mount_path : ""
  s3_shared_mount_enabled = var.s3_shared_files_enabled
  s3_shared_volume_name   = var.s3_shared_files_enabled ? module.s3_shared_mount[0].volume_name : ""
  s3_shared_mount_path    = var.s3_shared_files_enabled ? module.s3_shared_mount[0].mount_path : ""

  depends_on = [
    module.kuberay_operator,
    module.eks_alb_controller,
    module.lustre_shared_mount,
    module.s3_shared_mount,
  ]
}

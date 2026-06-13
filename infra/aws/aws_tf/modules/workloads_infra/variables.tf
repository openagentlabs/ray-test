variable "alb_controller_chart_version" {
  description = "Helm chart version for the AWS Load Balancer Controller."
  type        = string
  default     = "1.11.0"
  nullable    = false
}

variable "alb_ingress_cidr_blocks" {
  description = "CIDR blocks allowed to reach the public ALB on HTTP/HTTPS."
  type        = list(string)
  default     = ["0.0.0.0/0"]
  nullable    = false
}

variable "alb_ingress_group_name" {
  description = "Default ALB ingress group for shared internet-facing load balancers."
  type        = string
  default     = "arb-public"
  nullable    = false
}

variable "application_log_group_arns" {
  description = "Application log group ARNs for observability IAM and Fargate logging."
  type        = list(string)
  default     = []
  nullable    = false
}

variable "application_log_group_names" {
  description = "Map of service key to application log group name."
  type        = map(string)
  default     = {}
  nullable    = false
}

variable "bastion_ssh_cidr_blocks" {
  description = "Optional CIDR blocks for SSH to bastion (empty disables SSH; prefer SSM Session Manager)."
  type        = list(string)
  default     = []
  nullable    = false
}

variable "cloudwatch_log_retention_in_days" {
  description = "Retention for EKS / Container Insights log groups."
  type        = number
  default     = 30
  nullable    = false
}

variable "cluster_name" {
  description = "EKS cluster name. Defaults to PRJ_SLUG (ray-test) when empty."
  type        = string
  default     = ""
  nullable    = false
}

variable "namespace" {
  description = "Kubernetes namespace for ARB workloads. Defaults to cluster_name when empty."
  type        = string
  default     = ""
  nullable    = false
}

variable "fargate_workloads_namespace_enabled" {
  description = "When true, ARB workloads namespace is scheduled on Fargate. Set false when all workloads run on EC2 (CSI mounts)."
  type        = bool
  default     = true
  nullable    = false
}

variable "solution" {
  description = "Solution-wide metadata propagated from the root module."
  type = object({
    name                   = string
    description            = string
    version                = string
    date                   = string
    account_id             = string
    region                 = string
    deployment_environment = string
    deployment_index       = string
    deployment_instance    = string
    deployment_key         = string
    deployed_at            = string
    deployed_by            = string
    expires_at             = string
    cost_code              = string
    department             = string
  })
  nullable = false
}

variable "vpc_cidr" {
  description = "CIDR for the dedicated EKS Fargate VPC when creating a new VPC."
  type        = string
  default     = "10.42.0.0/16"
  nullable    = false
}

variable "existing_vpc_id" {
  description = "Reuse an existing VPC instead of creating one."
  type        = string
  default     = ""
  nullable    = false
}

variable "single_nat_gateway_enabled" {
  description = "When true, provision one NAT gateway for private subnet egress (cost-efficient)."
  type        = bool
  default     = true
  nullable    = false
}

variable "vpc_endpoints_enabled" {
  description = "Create VPC endpoints for private EKS/bastion connectivity (ECR, S3, SSM, Logs)."
  type        = bool
  default     = true
  nullable    = false
}

variable "workload_container_ports" {
  description = "TCP ports on EKS workloads that the ALB may forward traffic to."
  type        = list(number)
  default     = [8802, 8803, 8804, 8805, 8806, 8807, 8808, 8809, 8810, 8811]
  nullable    = false
}

variable "existing_subnet_ids" {
  description = "Public subnet IDs in existing_vpc_id for EKS Fargate."
  type        = list(string)
  default     = []
  nullable    = false
}

variable "kuberay_enabled" {
  description = "When true, provision the Ray EC2 node group (if needed), KubeRay operator, and RayCluster with ALB dashboard ingress."
  type        = bool
  default     = false
  nullable    = false
}

variable "kuberay_namespace" {
  description = "Kubernetes namespace for KubeRay and RayCluster."
  type        = string
  default     = "kuberay"
  nullable    = false
}

variable "kuberay_operator_chart_version" {
  description = "Helm chart version for the KubeRay operator."
  type        = string
  default     = "1.6.1"
  nullable    = false
}

variable "kuberay_ray_cluster_chart_version" {
  description = "Helm chart version for the KubeRay ray-cluster chart."
  type        = string
  default     = "1.6.1"
  nullable    = false
}

variable "ray_alb_ingress_group_name" {
  description = "ALB ingress group for the Ray dashboard and metrics."
  type        = string
  default     = "arb-ray"
  nullable    = false
}

variable "ray_image_repository" {
  description = "Container image repository for Ray head and worker pods."
  type        = string
  default     = "rayproject/ray"
  nullable    = false
}

variable "ray_image_tag" {
  description = "Ray version tag for head and worker containers."
  type        = string
  default     = "2.55.1"
  nullable    = false
}

variable "ray_node_count" {
  description = "Fixed EC2 node count for the Ray compute pool (8 vCPU / 32 GiB per node with m6i.2xlarge)."
  type        = number
  default     = 3
  nullable    = false
}

variable "ray_node_instance_type" {
  description = "EC2 instance type for the Ray managed node group."
  type        = string
  default     = "m6i.2xlarge"
  nullable    = false
}

variable "ray_worker_max_replicas" {
  description = "Maximum Ray worker pod replicas within the fixed node pool."
  type        = number
  default     = 2
  nullable    = false
}

variable "ray_worker_min_replicas" {
  description = "Minimum Ray worker pod replicas."
  type        = number
  default     = 2
  nullable    = false
}

variable "fsx_lustre_enabled" {
  description = "When true, provision FSx for Lustre and mount shared-lustre at /mnt/lustre on Ray EC2 pods."
  type        = bool
  default     = false
  nullable    = false
}

variable "fsx_lustre_storage_capacity_gib" {
  description = "FSx for Lustre storage capacity in GiB (minimum 1200)."
  type        = number
  default     = 1200
  nullable    = false
}

variable "fsx_lustre_deployment_type" {
  description = "FSx for Lustre deployment type."
  type        = string
  default     = "PERSISTENT_2"
  nullable    = false
}

variable "fsx_lustre_csi_chart_version" {
  description = "Helm chart version for the AWS FSx CSI driver."
  type        = string
  default     = "1.9.0"
  nullable    = false
}

variable "s3_shared_files_bucket_arn" {
  description = "ARN of the shared S3 bucket to mount (from root module.s3_shared_files)."
  type        = string
  default     = ""
  nullable    = false
}

variable "s3_shared_files_bucket_name" {
  description = "Name of the shared S3 bucket to mount (from root module.s3_shared_files)."
  type        = string
  default     = ""
  nullable    = false
}

variable "s3_shared_files_csi_addon_version" {
  description = "EKS add-on version for aws-mountpoint-s3-csi-driver (empty uses latest compatible)."
  type        = string
  default     = ""
  nullable    = false
}

variable "s3_shared_files_enabled" {
  description = "When true, install Mountpoint S3 CSI and mount shared-s3-files at /mnt/s3-files on Ray EC2 pods."
  type        = bool
  default     = false
  nullable    = false
}

variable "s3_shared_files_key_prefix" {
  description = "S3 key prefix exposed inside mounted pods."
  type        = string
  default     = "shared/"
  nullable    = false
}

variable "ray_node_pool_label_key" {
  description = "Node label key for EC2 Ray compute pool (manager-web shared mounts)."
  type        = string
  default     = "ray.io/node-pool"
  nullable    = false
}

variable "ray_node_pool_label_value" {
  description = "Node label value for EC2 Ray compute pool (manager-web shared mounts)."
  type        = string
  default     = "ray"
  nullable    = false
}

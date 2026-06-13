variable "alb_ingress_group_name" {
  description = "ALB ingress group for the Ray dashboard and API (dedicated internet-facing ALB)."
  type        = string
  default     = "arb-ray"
  nullable    = false
}

variable "chart_version" {
  description = "Helm chart version for the KubeRay ray-cluster chart."
  type        = string
  default     = "1.6.1"
  nullable    = false
}

variable "ingress_class" {
  description = "IngressClass for ALB-backed Ray dashboard ingress."
  type        = string
  default     = "alb"
  nullable    = false
}

variable "namespace" {
  description = "Kubernetes namespace for the RayCluster."
  type        = string
  nullable    = false
}

variable "node_pool_label_key" {
  description = "Node label key for Ray head and worker pods."
  type        = string
  nullable    = false
}

variable "node_pool_label_value" {
  description = "Node label value for Ray head and worker pods."
  type        = string
  nullable    = false
}

variable "ray_image_repository" {
  description = "Container image repository for Ray head and worker pods."
  type        = string
  default     = "rayproject/ray"
  nullable    = false
}

variable "ray_image_tag" {
  description = "Container image tag for Ray head and worker pods."
  type        = string
  default     = "2.55.1"
  nullable    = false
}

variable "release_name" {
  description = "Helm release name for the RayCluster chart."
  type        = string
  default     = "ray-cluster"
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

variable "lustre_mount_enabled" {
  description = "When true, mount the shared-lustre PVC at lustre_mount_path in Ray head and worker pods."
  type        = bool
  default     = false
  nullable    = false
}

variable "lustre_mount_path" {
  description = "Container mount path for the shared Lustre volume."
  type        = string
  default     = "/mnt/lustre"
  nullable    = false
}

variable "lustre_volume_name" {
  description = "Kubernetes volume name for the shared Lustre PVC."
  type        = string
  default     = "shared-lustre"
  nullable    = false
}

variable "s3_shared_mount_enabled" {
  description = "When true, mount the shared-s3-files PVC at s3_shared_mount_path in Ray head and worker pods."
  type        = bool
  default     = false
  nullable    = false
}

variable "s3_shared_mount_path" {
  description = "Container mount path for the shared S3-backed volume."
  type        = string
  default     = "/mnt/s3-files"
  nullable    = false
}

variable "s3_shared_volume_name" {
  description = "Kubernetes volume name for the shared S3 PVC."
  type        = string
  default     = "shared-s3-files"
  nullable    = false
}

variable "worker_max_replicas" {
  description = "Maximum Ray worker replicas (fixed node pool caps autoscaling)."
  type        = number
  default     = 2
  nullable    = false
}

variable "worker_min_replicas" {
  description = "Minimum Ray worker replicas."
  type        = number
  default     = 2
  nullable    = false
}

variable "mount_health_image" {
  description = "Container image for shared-mount init and watchdog sidecar containers on Ray pods."
  type        = string
  default     = "alpine:3.21"
  nullable    = false
}

variable "mount_health_wait_seconds" {
  description = "Maximum seconds the init container waits for lustre/S3 mounts before failing the pod."
  type        = number
  default     = 600
  nullable    = false
}

variable "mount_health_probe_max_attempts" {
  description = "Per-path probe retries for transient mount errors (EIO, ESTALE, etc.)."
  type        = number
  default     = 5
  nullable    = false
}

variable "mount_health_watchdog_interval_seconds" {
  description = "Seconds between shared-mount health checks in the Ray watchdog sidecar."
  type        = number
  default     = 30
  nullable    = false
}

variable "mount_pod_fs_group" {
  description = "fsGroup for Ray pods mounting shared Lustre/S3 volumes (aligns with rayproject/ray uid/gid 1000)."
  type        = number
  default     = 1000
  nullable    = false
}

variable "mount_pod_run_as_user" {
  description = "runAsUser for the Ray container when shared mounts are enabled."
  type        = number
  default     = 1000
  nullable    = false
}

variable "mount_pod_run_as_group" {
  description = "runAsGroup for the Ray container when shared mounts are enabled."
  type        = number
  default     = 1000
  nullable    = false
}

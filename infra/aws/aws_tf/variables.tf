variable "aws_account_id" {
  description = "AWS account ID this stack deploys into. Must equal AWS_ACCOUNT_ID in .cursor/rules/constants/constants.mdc."
  type        = string
  default     = "017868795096"
  nullable    = false
  validation {
    condition     = var.aws_account_id == "017868795096"
    error_message = "Account binding violated: this repo deploys only to the account in constants.mdc."
  }
}

variable "aws_region" {
  description = "AWS region this stack deploys into. Must equal AWS_DEFAULT_REGION in .cursor/rules/constants/constants.mdc."
  type        = string
  default     = "us-east-1"
  nullable    = false
}

variable "solution_date" {
  description = "ISO-8601 (YYYY-MM-DD) release date of this version."
  type        = string
  nullable    = false
  validation {
    condition     = can(regex("^\\d{4}-\\d{2}-\\d{2}$", var.solution_date))
    error_message = "solution_date must be YYYY-MM-DD."
  }
}

variable "solution_description" {
  description = "Human-readable description of what this stack provisions."
  type        = string
  nullable    = false
}

variable "solution_name" {
  description = "Short slug for the solution (lower_snake_case)."
  type        = string
  nullable    = false
  validation {
    condition     = can(regex("^[a-z][a-z0-9_]*$", var.solution_name))
    error_message = "solution_name must be lower_snake_case starting with a letter."
  }
}

variable "solution_version" {
  description = "Semantic version (MAJOR.MINOR.PATCH) of this infrastructure release."
  type        = string
  nullable    = false
  validation {
    condition     = can(regex("^[0-9]+\\.[0-9]+\\.[0-9]+$", var.solution_version))
    error_message = "solution_version must be semver, e.g. 0.1.0."
  }
}

variable "deployment_environment" {
  description = "Deployment environment slug: dev, prod, or uat. Part of deployment_key (single hyphens: dev-0001-a1b2c3)."
  type        = string
  nullable    = false
  validation {
    condition     = contains(["dev", "prod", "uat"], var.deployment_environment) && !can(regex("--", var.deployment_environment))
    error_message = "deployment_environment must be one of: dev, prod, uat — no '--' in the value."
  }
}

variable "deployment_index" {
  description = "Four-digit deployment version index (0001–9999). Part of deployment_key (single hyphens only)."
  type        = string
  nullable    = false
  validation {
    condition     = can(regex("^[0-9]{4}$", var.deployment_index)) && parseint(var.deployment_index, 10) >= 1 && !can(regex("--", var.deployment_index))
    error_message = "deployment_index must be a four-digit string from 0001 to 9999 — no '--' in the value."
  }
}

variable "deployment_instance" {
  description = "Six-character lowercase instance id [a-z0-9] separating parallel deployments in the same account."
  type        = string
  nullable    = false
  validation {
    condition     = can(regex("^[a-z0-9]{6}$", var.deployment_instance)) && !can(regex("--", var.deployment_instance))
    error_message = "deployment_instance must be exactly six lowercase letters or digits — no '--' in the value."
  }
}

variable "deployment_key_override" {
  description = <<-EOT
    Optional full deployment_key when live AWS resources use a legacy key (e.g. dev--0001--a1b2c3).
    Leave empty for canonical single-hyphen keys from deployment_environment/index/instance.
    Set in infra/envs/<env>/terraform.tfvars to align Terraform with an existing stack without rename.
  EOT
  type        = string
  default     = ""
  nullable    = false
}

variable "deployed_at" {
  description = "UTC ISO-8601 timestamp when this deployment was applied (e.g. 2026-06-11T14:30:00Z)."
  type        = string
  nullable    = false
  validation {
    condition     = can(regex("^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}Z$", var.deployed_at))
    error_message = "deployed_at must be UTC ISO-8601, e.g. 2026-06-11T14:30:00Z."
  }
}

variable "deployed_by" {
  description = "Email address of the engineer or automation principal that deployed this stack."
  type        = string
  nullable    = false
  validation {
    condition     = can(regex("^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}$", var.deployed_by))
    error_message = "deployed_by must be a valid email address."
  }
}

variable "expires_at" {
  description = "UTC ISO-8601 timestamp when this deployment expires and resources should be deleted. Use \"\" (TAG_EMPTY) when no expiry is planned."
  type        = string
  nullable    = false
  default     = ""
  validation {
    condition = (
      trimspace(var.expires_at) == "" ||
      can(regex("^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}Z$", var.expires_at))
    )
    error_message = "expires_at must be empty or UTC ISO-8601, e.g. 2026-12-11T14:30:00Z."
  }
}

variable "resource_owner" {
  description = "Accountable owner for tag ResourceOwner (email or team id)."
  type        = string
  nullable    = false
}

variable "owner_email" {
  description = "Owner contact email (tag OwnerEmail)."
  type        = string
  nullable    = false
  validation {
    condition     = can(regex("^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}$", var.owner_email))
    error_message = "owner_email must be a valid email address."
  }
}

variable "created_by" {
  description = "Email of the principal that created this stack (tag CreatedBy)."
  type        = string
  nullable    = false
  validation {
    condition     = can(regex("^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}$", var.created_by))
    error_message = "created_by must be a valid email address."
  }
}

variable "automation_ignore" {
  description = "When true, tag AutomationIgnore=true so repo automation skips these resources."
  type        = bool
  nullable    = false
  default     = false
}

variable "resource_group_1" {
  description = "Optional sub-grouping tag ResourceGroup1 (TAG_EMPTY when unused)."
  type        = string
  nullable    = false
  default     = ""
}

variable "resource_group_2" {
  description = "Optional sub-grouping tag ResourceGroup2 (TAG_EMPTY when unused)."
  type        = string
  nullable    = false
  default     = ""
}

variable "resource_group_3" {
  description = "Optional sub-grouping tag ResourceGroup3 (TAG_EMPTY when unused)."
  type        = string
  nullable    = false
  default     = ""
}

variable "cost_code" {
  description = "Finance cost code for chargeback (tag CostCode)."
  type        = string
  nullable    = false
}

variable "department" {
  description = "Owning department name (tag Department)."
  type        = string
  nullable    = false
}

variable "cost_center" {
  description = "Optional cost center for Cost Explorer allocation (tag CostCenter). Defaults to cost_code when empty."
  type        = string
  default     = ""
  nullable    = false
}

variable "general_ai_agent_bedrock_foundation_model_id" {
  description = <<-EOT
    Bedrock foundation model id (no ARN prefix), e.g. anthropic.claude-sonnet-4-5-20250929-v1:0.
    IAM allows bedrock:Converse / InvokeModel on
    arn:aws:bedrock:<aws_region>::foundation-model/<id>.
    Set to "" to omit that ARN from the policy. Must match general.ai.agent.svc `app_config.toml`
    `[agent.bedrock].foundation_model_id`.
  EOT
  type        = string
  nullable    = false
  default     = "anthropic.claude-sonnet-4-5-20250929-v1:0"
}

variable "notification_sns_email_subscription_endpoints" {
  description = <<-EOT
    Optional list of email addresses to subscribe to the notification SNS topic (protocol `email`).
    Recipients must confirm via AWS email before notification.svc publishes reach them.
  EOT
  type        = list(string)
  nullable    = false
  default     = []
}

variable "containers_eks_enabled" {
  description = <<-EOT
    When true, provision EKS (Fargate-only), ECR repositories, and IRSA roles for ARB workloads.
    Deploy pods with Helm via `make run-aws`. Push images with `make push-app-aws`.
  EOT
  type        = bool
  default     = false
  nullable    = false
}

variable "containers_cluster_name" {
  description = "EKS cluster name override. Empty uses PRJ_SLUG (solution_slug). Set for legacy stacks whose cluster name includes deployment_key."
  type        = string
  default     = ""
  nullable    = false
}

variable "containers_k8s_namespace" {
  description = "Kubernetes namespace for ARB workloads. Empty uses solution_slug. Set to match an existing cluster namespace."
  type        = string
  default     = ""
  nullable    = false
}

variable "containers_image_tag" {
  description = "Default container image tag for Kubernetes Deployments."
  type        = string
  default     = "latest"
  nullable    = false
}

variable "containers_workload_extra_environment" {
  description = <<-EOT
    Committed per-APP_ENV static pod environment (APP_ENV, APP_TARGET, gRPC hosts).
  See `infra/envs/<env>/k8s.tfvars`. Not modified by deploy scripts.
  EOT
  type        = map(map(string))
  default     = {}
  nullable    = false
}

variable "containers_workload_secret_environment" {
  description = <<-EOT
    Gitignored secrets from `make/scaffold_secrets.py` (`infra/envs/<env>/secrets.auto.tfvars`).
  Merged with containers_workload_extra_environment at apply time.
  EOT
  type        = map(map(string))
  default     = {}
  nullable    = false
}

variable "containers_workloads" {
  description = <<-EOT
    Enable/disable EKS Fargate workloads. Keys match containers_stack workload_catalog.
    Override image_tag per workload via optional image_tag field.
  EOT
  type = map(object({
    enabled   = optional(bool, true)
    image_tag = optional(string)
  }))
  default  = {}
  nullable = false
}

variable "containers_fargate_workloads_namespace_enabled" {
  description = "When false, workloads namespace pods schedule on EC2 only (required for FSx/S3 CSI mounts on manager-web)."
  type        = bool
  default     = true
  nullable    = false
}

variable "containers_existing_vpc_id" {
  description = "Reuse an existing VPC for EKS instead of creating a new one (avoids VPC quota errors)."
  type        = string
  default     = ""
  nullable    = false
}

variable "containers_existing_subnet_ids" {
  description = "Public subnet IDs in containers_existing_vpc_id for EKS Fargate (minimum two AZs)."
  type        = list(string)
  default     = []
  nullable    = false
}

variable "kuberay_enabled" {
  description = "When true (with containers_eks_enabled), provision Ray EC2 nodes, KubeRay operator, RayCluster, and ALB dashboard ingress."
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
  description = "ALB ingress group for Ray dashboard, API, and metrics."
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
  description = "Fixed EC2 node count for the Ray compute pool."
  type        = number
  default     = 3
  nullable    = false
}

variable "ray_node_instance_type" {
  description = "EC2 instance type for the Ray managed node group (default m6i.2xlarge = 8 vCPU / 32 GiB)."
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
  description = "When true (with containers_eks_enabled and Ray EC2 workloads), provision FSx for Lustre and mount shared-lustre at /mnt/lustre."
  type        = bool
  default     = false
  nullable    = false
}

variable "fsx_lustre_storage_capacity_gib" {
  description = "FSx for Lustre storage capacity in GiB (minimum 1200)."
  type        = number
  default     = 1200
  nullable    = false

  validation {
    condition     = var.fsx_lustre_storage_capacity_gib >= 1200
    error_message = "fsx_lustre_storage_capacity_gib must be at least 1200."
  }
}

variable "fsx_lustre_deployment_type" {
  description = "FSx for Lustre deployment type (SCRATCH_1, SCRATCH_2, PERSISTENT_1, PERSISTENT_2)."
  type        = string
  default     = "PERSISTENT_2"
  nullable    = false

  validation {
    condition     = contains(["SCRATCH_1", "SCRATCH_2", "PERSISTENT_1", "PERSISTENT_2"], var.fsx_lustre_deployment_type)
    error_message = "fsx_lustre_deployment_type must be SCRATCH_1, SCRATCH_2, PERSISTENT_1, or PERSISTENT_2."
  }
}

variable "fsx_lustre_csi_chart_version" {
  description = "Helm chart version for the AWS FSx CSI driver."
  type        = string
  default     = "1.9.0"
  nullable    = false
}

variable "s3_shared_files_enabled" {
  description = "When true (with containers_eks_enabled and Ray EC2 workloads), provision a shared S3 bucket and mount shared-s3-files at /mnt/s3-files."
  type        = bool
  default     = false
  nullable    = false
}

variable "s3_shared_files_key_prefix" {
  description = "S3 key prefix exposed inside mounted pods (trailing slash recommended)."
  type        = string
  default     = "shared/"
  nullable    = false
}

variable "s3_shared_files_csi_addon_version" {
  description = "EKS add-on version for aws-mountpoint-s3-csi-driver (empty uses latest compatible)."
  type        = string
  default     = ""
  nullable    = false
}

variable "general_ai_agent_bedrock_inference_profile_id" {
  description = <<-EOT
    Bedrock application inference profile id, e.g. us.anthropic.claude-sonnet-4-5-20250929-v1:0.
    IAM allows converse on
    arn:aws:bedrock:<aws_region>:<aws_account_id>:inference-profile/<id>.
    Set to "" to omit that ARN. Must match `app_config.toml` `[agent.bedrock].inference_profile_id`
    (and usually `[agent.bedrock].strands_model_id`).
  EOT
  type        = string
  nullable    = false
  default     = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"
}

variable "arch_diagram_agent_bedrock_foundation_model_id" {
  description = <<-EOT
    Bedrock Claude foundation model id for arch.diagram.agent.svc (no ARN prefix).
    IAM allows bedrock:Converse / InvokeModel on
    arn:aws:bedrock:<aws_region>::foundation-model/<id>.
    Must match arch.diagram.agent.svc `app_config.toml` `[agent.bedrock].foundation_model_id`.
  EOT
  type        = string
  nullable    = false
  default     = "anthropic.claude-sonnet-4-5-20250929-v1:0"
}

variable "document_storage_bedrock_embed_model_ids" {
  description = <<-EOT
    Bedrock Titan embedding model ids for document-storage.svc vector search.
    IAM allows bedrock:InvokeModel on arn:aws:bedrock:<aws_region>::foundation-model/<id>.
    Must match `app_config.toml` `[opensearch].bedrock_model_id` and image embed usage in code.
  EOT
  type        = list(string)
  nullable    = false
  default = [
    "amazon.titan-embed-text-v2:0",
    "amazon.titan-embed-image-v1:0",
  ]
}

variable "arch_diagram_agent_bedrock_inference_profile_id" {
  description = <<-EOT
    Bedrock Claude inference profile id for arch.diagram.agent.svc.
    IAM allows converse on
    arn:aws:bedrock:<aws_region>:<aws_account_id>:inference-profile/<id>.
    Must match `app_config.toml` `[agent.bedrock].inference_profile_id`
    (and usually `[agent.bedrock].strands_model_id`).
  EOT
  type        = string
  nullable    = false
  default     = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"
}

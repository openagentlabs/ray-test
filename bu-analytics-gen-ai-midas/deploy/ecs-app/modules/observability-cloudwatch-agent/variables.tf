variable "environment" {
  description = "Deployment environment (dev, uat, prod). Used in ECR repo names and tags."
  type        = string
}

variable "aws_region" {
  description = "AWS region. Must be us-east-1 for MIDAS."
  type        = string
  default     = "us-east-1"
}

variable "aws_account_id" {
  description = "AWS account ID. Used to build the private ECR image URLs (no NAT/IGW so nodes cannot reach public.ecr.aws)."
  type        = string
}

variable "eks_cluster_name" {
  description = "Name of the EKS cluster (e.g. midas-eks-dev). Used as the IRSA role name prefix and as the chart clusterName value."
  type        = string
}

variable "eks_cluster_endpoint" {
  description = "EKS cluster API server endpoint. Used by the Helm provider exec authenticator (passed through from the root module, same pattern as observability-fluent-bit)."
  type        = string
}

variable "eks_cluster_ca" {
  description = "Base64-encoded cluster CA certificate data. Used by the Helm provider."
  type        = string
}

variable "oidc_provider_arn" {
  description = "ARN of the IAM OIDC identity provider for the EKS cluster. Used as the Federated principal for the IRSA trust policy. Pass module.eks_alb_controller_iam.oidc_provider_arn from the root module."
  type        = string
}

variable "oidc_issuer_url" {
  description = "EKS OIDC issuer URL (e.g. https://oidc.eks.us-east-1.amazonaws.com/id/XXXX). Used to build the StringEquals condition keys for the IRSA trust policy."
  type        = string
}

variable "kubernetes_namespace" {
  description = "Namespace where the CloudWatch Agent + operator are installed. The chart creates this namespace itself; default matches AWS documentation."
  type        = string
  default     = "amazon-cloudwatch"
}

variable "agent_service_account_name" {
  description = "Service account name used by the CloudWatch Agent DaemonSet pods. Must match the chart's agent.serviceAccount.name. The IRSA trust policy uses this in its sub: claim."
  type        = string
  default     = "cloudwatch-agent"
}

variable "chart_version" {
  description = "Helm chart version for amazon-cloudwatch-observability (https://aws-observability.github.io/helm-charts). Pinned to a known good release; bump when validating a newer agent build. NOTE: the 4.x series jumps 4.1.0 -> 4.2.0 (no 4.1.1), pick from the upstream index.yaml."
  type        = string
  default     = "4.10.3"
}

variable "agent_image_tag" {
  description = "Tag of the cloudwatch-agent container image mirrored into private ECR. Must match the tag bundled with chart_version (see upstream values.yaml under agent.image.tag) AND the tag in deploy/scripts/ci/mirror-addon-images-ecr.sh."
  type        = string
  default     = "1.300064.1b1344"
}

variable "operator_image_tag" {
  description = "Tag of the cloudwatch-agent-operator container image mirrored into private ECR. Must match the tag bundled with chart_version (see upstream values.yaml under manager.image.tag) AND the tag in deploy/scripts/ci/mirror-addon-images-ecr.sh. NOTE: the operator binary changes its CLI flag set across versions (e.g. --auto-monitor-config was added after 2.x), so this MUST match the chart, not a pinned older tag."
  type        = string
  default     = "3.3.2"
}

variable "container_logs_enabled" {
  description = "When true, the chart also deploys its bundled Fluent Bit for container log shipping. MIDAS already runs aws-for-fluent-bit (deploy/ecs-app/modules/observability-fluent-bit) so this is false to avoid duplicate log pipelines."
  type        = bool
  default     = false
}

variable "tags" {
  description = "Additional tags to merge onto AWS resources (ECR repos, IAM role)."
  type        = map(string)
  default     = {}
}

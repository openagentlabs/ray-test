variable "aws_region" {
  type        = string
  description = "AWS region for ECR and IAM resources."
  default     = "us-east-1"
}

variable "environment" {
  type        = string
  description = "Environment name (e.g. dev, staging, prod)."
  default     = "dev"
}

variable "service_name" {
  type        = string
  description = "Must match router.svc [app].service_name."
  default     = "router-svc"
}

variable "database_url_secret_arn" {
  type        = string
  default     = ""
  description = "Secrets Manager ARN holding the shared Postgres DATABASE_URL. Empty to skip the IAM read policy (DSN injected via Kubernetes Secret instead)."
}

variable "db_table_prefix" {
  type        = string
  default     = "pm_"
  description = "Prefix for the routing-tier tables in the shared Postgres database (must match [postgres].table_prefix / Helm podManager.postgres.tablePrefix)."
}

variable "eks_cluster_name" {
  type        = string
  default     = null
  description = "EKS cluster name; defaults to {environment}-pod-manager."
}

variable "eks_cluster_version" {
  type        = string
  default     = "1.29"
  description = "EKS Kubernetes version."
}

variable "eks_node_instance_types" {
  type        = list(string)
  default     = ["t3.medium"]
  description = "Managed node group instance types."
}

variable "eks_node_desired_size" {
  type        = number
  default     = 2
  description = "Desired EKS node count."
}

variable "eks_node_min_size" {
  type        = number
  default     = 2
  description = "Minimum EKS node count."
}

variable "eks_node_max_size" {
  type        = number
  default     = 4
  description = "Maximum EKS node count."
}

variable "vpc_cidr" {
  type        = string
  default     = "10.0.0.0/16"
  description = "VPC CIDR block."
}

variable "private_subnet_cidrs" {
  type        = list(string)
  default     = ["10.0.1.0/24", "10.0.2.0/24"]
  description = "Private subnet CIDR blocks (one per AZ)."
}

variable "public_subnet_cidrs" {
  type        = list(string)
  default     = ["10.0.101.0/24", "10.0.102.0/24"]
  description = "Public subnet CIDR blocks (one per AZ)."
}

variable "create_vpc" {
  type        = bool
  default     = true
  description = "Create a new VPC; set false to reuse an existing VPC (e.g. when at VPC quota)."
}

variable "existing_vpc_id" {
  type        = string
  default     = null
  description = "Existing VPC ID when create_vpc=false."
}

variable "existing_private_subnet_ids" {
  type        = list(string)
  default     = []
  description = "Private subnet IDs for EKS when create_vpc=false."
}

variable "kubernetes_namespace" {
  type        = string
  default     = "routing"
  description = "Namespace for the routing-tier Helm release."
}

variable "kubernetes_service_account" {
  type        = string
  default     = "pod-manager"
  description = "Service account name for router.svc IRSA."
}

variable "iam_role_name" {
  type        = string
  default     = null
  description = "Override IAM role name; defaults to {environment}-pod-manager-irsa."
}

variable "ecr_repository_names" {
  type = list(string)
  default = [
    "envoy-router",
    "router-svc",
    "backend-pool-node",
    "login-pod",
  ]
  description = "ECR repositories for routing-tier and test backend images."
}

variable "aws_account_id" {
  type        = string
  description = "AWS account ID (passed from the ecs-app root module)."
}

variable "environment" {
  type        = string
  description = "Tenant environment (e.g. dev, uat, prod) - matches Jenkins TENANT_ENV."
}

variable "aws_region" {
  type        = string
  description = "AWS region"
  default     = "us-east-1"
}

variable "cluster_name_prefix" {
  description = "Prefix for the EKS cluster name; final name is {prefix}-{environment}"
  type        = string
  default     = "midas-eks"
}

variable "vpc_id" {
  description = "Existing VPC ID (centrally managed). Must match all subnets."
  type        = string
}

variable "cluster_subnet_ids" {
  description = "Subnets for the EKS control plane ENIs. Must span at least 2 AZs (managed node group requirement)."
  type        = list(string)
}

variable "node_subnet_ids" {
  description = "Subnets for worker nodes; defaults to cluster_subnet_ids if null."
  type        = list(string)
  default     = null
}

variable "kubernetes_version" {
  description = "EKS Kubernetes version (e.g. 1.30); must not be lower than the cluster's current version (EKS does not support downgrades)."
  type        = string
  default     = "1.30"
}

variable "cluster_enabled_log_types" {
  description = "Control plane log types to send to CloudWatch"
  type        = list(string)
  default     = ["api", "audit", "authenticator", "controllerManager", "scheduler"]
}

variable "cluster_log_retention_days" {
  description = "Retention for /aws/eks/{cluster}/cluster log group"
  type        = number
  default     = 30
}

variable "node_instance_types" {
  description = "EC2 instance types for the managed node group (e.g. m6i.4xlarge: 16 vCPU, 64 GiB). Keep midas-api-backend-svc Helm requests below this shape Allocatable (default chart uses 14600m CPU / 53Gi plus node slack)."
  type        = list(string)
  default     = ["m6i.4xlarge"]
}

variable "node_desired_size" {
  type    = number
  default = 2
}

variable "node_min_size" {
  type        = number
  default     = 2
  description = "ASG minimum; keep in sync with root eks_node_min_size (MIDAS defaults to 2 workers)."
}

variable "node_max_size" {
  type    = number
  default = 4
}

variable "node_disk_size" {
  description = "Root volume size (GiB) for nodes"
  type        = number
  default     = 50
}

variable "node_capacity_type" {
  description = "ON_DEMAND or SPOT (dev may use SPOT for cost - confirm org policy)"
  type        = string
  default     = "ON_DEMAND"
}

variable "node_ami_type" {
  description = "EKS AL2_x86_64, BOTTLEROCKET_x86_64, etc."
  type        = string
  default     = "AL2_x86_64"
}

variable "attach_ssm_policy_to_nodes" {
  description = "Attach AmazonSSMManagedInstanceCore to node role for SSM-based troubleshooting"
  type        = bool
  default     = true
}

variable "cluster_api_https_ingress_cidrs" {
  description = "CIDRs allowed TCP 443 ingress to the EKS cluster security group (Kubernetes API when reachable from those networks). Empty skips the rule."
  type        = list(string)
  default     = []
}

variable "tags" {
  description = "Extra tags for EKS resources"
  type        = map(string)
  default     = {}
}

# CKV_AWS_58: optional envelope encryption of Kubernetes secrets with a customer-managed KMS key.
# Empty string disables encryption_config (dev default — leaves the cluster API unchanged so
# existing clusters do not require replacement). Set to a CMK ARN to enable encryption on
# *new* clusters or during a planned maintenance window (adding/removing this attribute on an
# existing cluster forces cluster replacement).
variable "secrets_kms_key_arn" {
  description = "KMS key ARN for EKS Kubernetes-secrets envelope encryption. Empty string skips encryption_config."
  type        = string
  default     = ""
}

# Fortify "Insecure EKS Storage": optional explicit launch template that pins
# EBS encryption to a customer-managed KMS key. Empty string = use managed-AMI
# defaults (current dev behaviour; AWS-managed encryption when account-level
# default EBS encryption is on). Set the var on prod tfvars to enable an
# explicit CMK without replacing existing node groups in dev.
variable "node_ebs_kms_key_arn" {
  description = "Optional KMS CMK ARN for EKS node EBS root volumes. Empty = managed-AMI defaults (dev)."
  type        = string
  default     = ""
}

locals {
  node_subnet_ids_effective = var.node_subnet_ids != null ? var.node_subnet_ids : var.cluster_subnet_ids
  all_subnet_ids            = toset(concat(var.cluster_subnet_ids, local.node_subnet_ids_effective))
}

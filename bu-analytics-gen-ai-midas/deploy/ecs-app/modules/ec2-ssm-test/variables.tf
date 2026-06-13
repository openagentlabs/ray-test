variable "aws_account_id" {
  type        = string
  description = "Workload AWS account ID (for tagging and naming)."
}

variable "environment" {
  type        = string
  description = "Environment name (e.g. dev, uat, prod)."
}

variable "resource_name_suffix" {
  type        = string
  description = "Suffix appended to midas-<env>-ec2-ssm-test for IAM/SG/instance names (e.g. \"-clone\"). Use \"\" for the primary jumpbox."
  default     = ""

  validation {
    condition     = can(regex("^[a-z0-9-]*$", var.resource_name_suffix)) && length(var.resource_name_suffix) <= 24
    error_message = "resource_name_suffix must be empty or lowercase letters, digits, hyphens only, max 24 chars (e.g. \"-clone\")."
  }
}

variable "vpc_id" {
  type        = string
  description = "VPC ID where the instance is placed (MIDAS workload VPC)."
}

variable "subnet_id" {
  type        = string
  description = "Explicit private subnet ID. Leave empty to auto-select SubnetGroup 1, else 2, else any subnet in the VPC (sorted for stability)."
  default     = ""
}

variable "instance_type" {
  type        = string
  description = "EC2 instance type. Default t2.micro is 1 vCPU (testing)."
  default     = "t2.micro"
}

variable "root_volume_size_gb" {
  type        = number
  description = "Root gp3 volume size in GB."
  default     = 20
}

variable "aws_region" {
  type        = string
  description = "AWS region (for EKS IAM resource ARNs when enable_eks_kubectl_iam is true)."
  default     = "us-east-1"
}

variable "enable_eks_kubectl_iam" {
  type        = bool
  description = "When true, attach an inline policy allowing eks:DescribeCluster (and list) for aws eks update-kubeconfig / get-token on the given cluster."
  default     = false
}

variable "eks_cluster_name" {
  type        = string
  description = "EKS cluster name (e.g. midas-eks-dev). Required when enable_eks_kubectl_iam is true."
  default     = ""
}

variable "eks_kubernetes_version" {
  type        = string
  description = "EKS control plane minor version (e.g. 1.30) used to pin kubectl download. Required when jump box kubectl install runs."
  default     = ""
}

variable "jumpbox_install_kubectl" {
  type        = bool
  nullable    = true
  description = <<-EOT
    When true, EC2 user_data installs AWS CLI v2 (if missing) and kubectl aligned to eks_kubernetes_version.
    Changing user_data or this flag typically replaces the jump box instance on next apply.
    If null, defaults to enable_eks_kubectl_iam (install when EKS kubeconfig IAM is enabled).
  EOT
  default     = null
}

variable "jumpbox_helm_version" {
  type        = string
  description = "Helm 3.x release to install on the jump box (e.g. 3.16.4). Used only when jump box user_data installs kubectl."
  default     = "3.16.4"
}

variable "s3_access_bucket_names" {
  type        = list(string)
  description = "S3 bucket names (not ARNs) the instance role may list and read/write objects on. Empty skips the inline IAM policy."
  default     = []
}

# Fortify "Insecure EC2 Storage": optional customer-managed KMS key for the
# jumpbox root EBS volume. Empty (default) leaves the volume encrypted with
# the AWS-managed EBS default key, which is acceptable for a non-data-bearing
# bastion. Set this in prod tfvars to pin a CMK.
variable "root_volume_kms_key_arn" {
  type        = string
  description = "Optional KMS CMK ARN for the jumpbox root EBS volume. Empty = AWS-managed key (dev default)."
  default     = ""
}

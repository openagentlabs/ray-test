variable "aws_account_id" {
  type        = string
  description = "Workload AWS account ID (for tagging and naming)."
}

variable "environment" {
  type        = string
  description = "Environment name (e.g. dev, uat, prod)."
}

variable "vpc_id" {
  type        = string
  description = "VPC ID where the instance is placed (same as the EKS cluster workload VPC)."
}

variable "subnet_id" {
  type        = string
  description = "Private subnet ID for the instance (use the Ubuntu ec2-ssm-test subnet for parity with jumpbox i-0342e59b40cd01082)."
}

variable "instance_type" {
  type        = string
  description = "EC2 instance type. t3.large (2 vCPU, 8 GiB) is a practical minimum for Windows Server test workloads."
  default     = "t3.large"
}

variable "root_volume_size_gb" {
  type        = number
  description = "Root gp3 volume size in GB (Windows base + patches benefit from at least 50)."
  default     = 50
}

variable "aws_region" {
  type        = string
  description = "AWS region (tags / naming only for this module)."
  default     = "us-east-1"
}

variable "enable_fleet_manager_bootstrap" {
  type        = bool
  description = "When true, first-boot user_data enables RDP service, firewall, PSReadLine, and SSM Agent refresh for Fleet Manager Remote Desktop."
  default     = true
}

variable "enable_eks_kubectl_iam" {
  type        = bool
  description = "When true and no shared jumpbox profile is set, attach inline IAM on this module's role (eks:DescribeCluster, eks:ListClusters) like ec2-ssm-test."
  default     = false
}

variable "bootstrap_install_eks_cli" {
  type        = bool
  description = "When true, user_data installs AWS CLI v2 and kubectl when cluster/version are set. Use with shared jumpbox role that already has EKS IAM (ec2-ssm-test)."
  default     = false
}

variable "eks_cluster_name" {
  type        = string
  description = "EKS cluster name (e.g. midas-eks-dev). Used for user_data kubectl URL when bootstrap_install_eks_cli is true; required when enable_eks_kubectl_iam is true on a dedicated role."
  default     = ""
}

variable "eks_kubernetes_version" {
  type        = string
  description = "EKS control plane version string for kubectl download in user_data (e.g. 1.30 or 1.30.9)."
  default     = ""
}

variable "shared_jumpbox_security_group_id" {
  type        = string
  description = "When set with shared_jumpbox_instance_profile_name, reuse the Ubuntu ec2-ssm-test security group (same SG-to-SG rules as i-0342e59b40cd01082). Leave empty to create a Windows-specific SG."
  default     = ""
}

variable "shared_jumpbox_instance_profile_name" {
  type        = string
  description = "When set with shared_jumpbox_security_group_id, reuse the ec2-ssm-test instance profile (same IAM role as i-0342e59b40cd01082). Leave empty to create a Windows-specific role and profile."
  default     = ""
}

variable "key_name" {
  type        = string
  description = "Optional EC2 key pair name for the Windows instance (set at launch). Empty string omits key_name."
  default     = ""
}

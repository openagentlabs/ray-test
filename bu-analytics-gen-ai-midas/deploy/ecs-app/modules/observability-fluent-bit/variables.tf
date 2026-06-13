variable "environment" {
  description = "Deployment environment (dev, uat, prod). Used in resource names and log group paths."
  type        = string
}

variable "aws_region" {
  description = "AWS region. Must be us-east-1 for MIDAS."
  type        = string
  default     = "us-east-1"
}

variable "aws_account_id" {
  description = "AWS account ID. Used to build the private ECR image URL."
  type        = string
}

variable "eks_cluster_name" {
  description = "Name of the EKS cluster (e.g. midas-eks-dev). Passed to helm_release as a dependency anchor."
  type        = string
}

variable "eks_cluster_endpoint" {
  description = "EKS cluster API server endpoint. Used by the Helm provider exec authenticator."
  type        = string
}

variable "eks_cluster_ca" {
  description = "Base64-encoded cluster CA certificate data. Used by the Helm provider."
  type        = string
}

variable "log_group_name" {
  description = "CloudWatch Log Group name to ship logs to. Should be the output of module.observability_app_logs.backend_application_log_group_name."
  type        = string
}

variable "chart_version" {
  description = "Helm chart version for aws-for-fluent-bit. Pin to a known good release."
  type        = string
  default     = "0.1.34"
}

variable "tags" {
  description = "Additional tags to merge onto ECR repository resource."
  type        = map(string)
  default     = {}
}

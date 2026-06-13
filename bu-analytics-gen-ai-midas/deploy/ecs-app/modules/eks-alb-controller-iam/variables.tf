variable "aws_account_id" {
  type        = string
  description = "Workload AWS account ID."
}

variable "environment" {
  type        = string
  description = "Environment (e.g. dev, uat, prod)."
}

variable "aws_region" {
  type        = string
  description = "AWS region (MIDAS: us-east-1 only)."
  default     = "us-east-1"
}

variable "cluster_name" {
  type        = string
  description = "EKS cluster name (e.g. midas-eks-dev)."
}

variable "oidc_issuer_url" {
  type        = string
  description = "OIDC issuer URL from the EKS cluster (identity.issuer)."
}

variable "kubernetes_namespace" {
  type        = string
  description = "Namespace for the AWS Load Balancer Controller service account."
  default     = "kube-system"
}

variable "service_account_name" {
  type        = string
  description = "Kubernetes service account name for the controller (IRSA subject)."
  default     = "aws-load-balancer-controller"
}

variable "tags" {
  type        = map(string)
  description = "Extra tags for IAM resources."
  default     = {}
}

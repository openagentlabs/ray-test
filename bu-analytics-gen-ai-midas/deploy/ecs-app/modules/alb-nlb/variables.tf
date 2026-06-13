variable "aws_account_id" {
  type        = string
  description = "AWS account ID (for tagging)."
}

variable "environment" {
  type        = string
  description = "Environment name (e.g. dev, uat, prod)."
}

variable "aws_region" {
  type        = string
  description = "AWS region."
  default     = "us-east-1"
}

variable "vpc_id" {
  type        = string
  description = "VPC ID where the NLB and ALB are placed."
}

variable "alb_subnet_ids" {
  type        = list(string)
  description = "Subnets for the internal ALB (at least 2 AZs; SubnetGroup 1 recommended for IP headroom)."
}

variable "nlb_subnet_ids" {
  type        = list(string)
  description = "Subnets for the internal NLB (at least 2 AZs; one ENI per AZ gives static private IPs)."
}

variable "nlb_corporate_ingress_cidrs" {
  type        = list(string)
  description = "CIDRs allowed TCP 443 ingress to the NLB (corporate/TGW-attached networks)."
  default     = []
}

variable "jumpbox_security_group_id" {
  type        = string
  description = "Security group ID of the SSM jumpbox (ec2-ssm-test) to allow direct ALB and NLB HTTPS testing."
}

variable "jumpbox_security_group_id_secondary" {
  type        = string
  description = "Optional second Linux SSM jumpbox SG (same NLB/ALB :443 ingress as jumpbox_security_group_id). Leave empty to skip."
  default     = ""
}

variable "jumpbox_secondary_ingress_enabled" {
  type        = bool
  description = "When true, create NLB/ALB ingress rules for jumpbox_security_group_id_secondary. Must be known at plan time (do not derive from the SG id string). Use the same flag as the root module uses to create the second jumpbox."
  default     = false
}

variable "jumpbox_windows_security_group_id" {
  type        = string
  description = "Optional security group ID of the Windows SSM test instance for the same NLB and ALB HTTPS testing as the Linux jumpbox. Leave empty to skip."
  default     = ""
}

variable "eks_cluster_security_group_id" {
  type        = string
  description = "EKS-managed cluster security group ID. No longer used for egress rules (CIDR-based now); kept for backwards compatibility — pass the cluster SG ID or an empty string."
  default     = ""
}

variable "vpc_cidr" {
  type        = string
  description = "VPC CIDR block (e.g. 10.72.134.0/23). Used for ALB egress rules to pods to avoid cross-SG references that cause DependencyViolation on SG destroy."
  default     = "10.72.134.0/23"
}

variable "certificate_arn" {
  type        = string
  description = "ACM certificate ARN (us-east-1) for the ALB HTTPS:443 listener. When empty, the ALB has no HTTPS listener and the NLB has no TCP:443 listener — deploy is a no-op until a cert is provided."
  default     = ""
}

variable "public_https_hostname" {
  type        = string
  description = "When non-empty, the /frontend, /backend, and /graph path listener rules also require a matching Host (this FQDN and the internal ALB DNS) so those prefixes align with the corporate URL. The default forward for / and other paths is unchanged."
  default     = ""
}

variable "backend_target_group_stickiness_seconds" {
  type        = number
  description = <<-EOT
    When > 0, the backend ALB target group enables lb_cookie stickiness with this
    cookie duration (seconds). MIDAS uses TargetGroupBinding (deploy/ecs-app/eks-tgb.tf),
    not Ingress, so the ALB controller cannot read stickiness off the Service
    annotation - it must be set on the target group itself. The DataFrameStateManager
    singleton (backend/app/services/dataframe_state_manager.py) lives per-pod, so
    pinning each user to one pod via this cookie avoids cross-pod state misses.
    Set 0 to disable stickiness explicitly. Default 86400 = 24 h.
  EOT
  default     = 86400

  validation {
    condition     = var.backend_target_group_stickiness_seconds >= 0 && var.backend_target_group_stickiness_seconds <= 604800
    error_message = "backend_target_group_stickiness_seconds must be between 0 and 604800 (7 days)."
  }
}

variable "deletion_protection" {
  type        = bool
  description = "When true, Terraform/API cannot delete the instance without disabling this first."
  # CKV_AWS_293: safe-by-default — callers must explicitly opt out (e.g. dev/test tfvars
  # setting deletion_protection = false) in order to allow `terraform destroy`.
  default = true
}

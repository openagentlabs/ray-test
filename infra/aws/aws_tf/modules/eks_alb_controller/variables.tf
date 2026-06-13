variable "alb_ingress_group_name" {
  description = "Default ALB ingress group name for shared internet-facing load balancers."
  type        = string
  default     = "arb-public"
  nullable    = false
}

variable "chart_version" {
  description = "Helm chart version for aws-load-balancer-controller (controller v2.x)."
  type        = string
  default     = "1.11.0"
  nullable    = false
}

variable "cluster_name" {
  description = "EKS cluster name the controller manages ALBs for."
  type        = string
  nullable    = false
}

variable "ingress_class" {
  description = "IngressClass name created and watched by the controller."
  type        = string
  default     = "alb"
  nullable    = false
}

variable "oidc_provider_arn" {
  description = "IAM OIDC provider ARN for IRSA."
  type        = string
  nullable    = false
}

variable "oidc_provider_url" {
  description = "OIDC issuer host (without https://) for IRSA trust policies."
  type        = string
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

variable "vpc_id" {
  description = "VPC ID where the controller provisions Application Load Balancers."
  type        = string
  nullable    = false
}

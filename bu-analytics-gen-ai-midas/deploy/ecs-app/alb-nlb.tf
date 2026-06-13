# -----------------------------------------------------------------------------
# Private NLB + ALB ingress for MIDAS EKS services — HTTPS-only.
#
# Traffic flow (corporate URL → Midas in VPC):
#   Internal/corporate DNS: FQDN → CNAME/alias to output nlb_dns_name (this NLB).
#   Then: NLB TCP:443 → ALB HTTPS:443 (TLS terminates) → EKS
#   → midas-web-frontend-svc :8080 / API :8000 / graph :8001 via TGBs
#
# Certificate:
#   Pass the ACM certificate ARN via var.alb_nlb_certificate_arn.
#   Supports ACM-issued and imported/self-signed certificates.
#   When empty, NLB+ALB deploy without HTTPS listeners (cert_ready=false in module).
#
# TargetGroupBindings (TGBs) are managed by Terraform in eks-tgb.tf.
# The AWS Load Balancer Controller registers pod IPs automatically.
# No manual kubectl apply is required after terraform apply.
# -----------------------------------------------------------------------------

module "alb_nlb" {
  count  = var.alb_nlb_enabled ? 1 : 0
  source = "./modules/alb-nlb"

  aws_account_id = var.aws_account_id
  environment    = var.environment
  aws_region     = var.aws_region

  vpc_id         = var.eks_vpc_id
  alb_subnet_ids = var.alb_subnet_ids
  nlb_subnet_ids = var.nlb_subnet_ids

  nlb_corporate_ingress_cidrs = var.nlb_corporate_ingress_cidrs

  # Direct ACM ARN — works for both ACM-issued and imported/self-signed certs.
  # Empty string disables HTTPS listeners until a cert ARN is provided.
  certificate_arn       = var.alb_nlb_certificate_arn
  public_https_hostname = var.alb_nlb_public_https_hostname

  # Backend ALB TG lb_cookie stickiness duration (seconds). Required because
  # MIDAS wires the backend via TargetGroupBinding, not Ingress, so stickiness
  # must live on the target group resource (see modules/alb-nlb/main.tf).
  backend_target_group_stickiness_seconds = var.backend_target_group_stickiness_seconds

  jumpbox_security_group_id           = module.ec2_ssm_test.security_group_id
  jumpbox_secondary_ingress_enabled   = var.ec2_ssm_test_clone_enabled
  jumpbox_security_group_id_secondary = var.ec2_ssm_test_clone_enabled ? module.ec2_ssm_test_clone[0].security_group_id : ""
  jumpbox_windows_security_group_id   = ""
  # eks_cluster_security_group_id kept for variable compatibility; egress rules now use vpc_cidr.
  eks_cluster_security_group_id = module.eks.eks_cluster_security_group_id
  vpc_cidr                      = "10.72.134.0/23"

  depends_on = [module.eks, module.ec2_ssm_test, module.ec2_ssm_windows_test]
}

# ---------------------------------------------------------------------------
# Outputs (only populated when alb_nlb_enabled = true)
# ---------------------------------------------------------------------------

output "alb_dns_name" {
  description = "Internal ALB DNS name (stable HTTPS endpoint). Empty when alb_nlb_enabled=false."
  value       = var.alb_nlb_enabled ? module.alb_nlb[0].alb_dns_name : ""
}

output "nlb_dns_name" {
  description = "CNAME/alias the Midas HTTPS FQDN (in internal/corporate DNS) to this so browsers hit NLB:443 then ALB. Empty when alb_nlb_enabled=false."
  value       = var.alb_nlb_enabled ? module.alb_nlb[0].nlb_dns_name : ""
}

output "nlb_arn" {
  description = "Internal NLB ARN. Empty when alb_nlb_enabled=false."
  value       = var.alb_nlb_enabled ? module.alb_nlb[0].nlb_arn : ""
}

output "alb_frontend_target_group_arn" {
  description = "ALB TG ARN for frontend pods (HTTP port 8080)."
  value       = var.alb_nlb_enabled ? module.alb_nlb[0].alb_frontend_target_group_arn : ""
}

output "alb_backend_target_group_arn" {
  description = "ALB TG ARN for backend pods (HTTP port 8000)."
  value       = var.alb_nlb_enabled ? module.alb_nlb[0].alb_backend_target_group_arn : ""
}

output "alb_graph_target_group_arn" {
  description = "ALB TG ARN for graph pods (HTTP port 8001)."
  value       = var.alb_nlb_enabled ? module.alb_nlb[0].alb_graph_target_group_arn : ""
}

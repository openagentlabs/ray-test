# -----------------------------------------------------------------------------
# IAM OIDC + IRSA for AWS Load Balancer Controller (Ingress → internal ALB).
# Helm install is documented under deploy/k8s/aws-load-balancer-controller/.
# -----------------------------------------------------------------------------

locals {
  eks_internal_alb_subnet_ids_effective = length(var.eks_internal_alb_subnet_ids) > 0 ? var.eks_internal_alb_subnet_ids : (
    var.eks_node_subnet_ids != null ? var.eks_node_subnet_ids : var.eks_cluster_subnet_ids
  )
}

module "eks_alb_controller_iam" {
  source = "./modules/eks-alb-controller-iam"

  aws_account_id  = var.aws_account_id
  environment     = var.environment
  aws_region      = var.aws_region
  cluster_name    = module.eks.eks_cluster_name
  oidc_issuer_url = module.eks.oidc_issuer_url
}

# Opt-in: tag subnets so the controller selects them for internal ALBs (private scheme only).
resource "aws_ec2_tag" "eks_internal_alb" {
  for_each = var.eks_internal_alb_subnet_tag_enabled ? toset(local.eks_internal_alb_subnet_ids_effective) : toset([])

  resource_id = each.value
  key         = "kubernetes.io/role/internal-elb"
  value       = "1"
}

output "eks_alb_controller_oidc_provider_arn" {
  description = "IAM OIDC provider ARN for the EKS cluster (IRSA)."
  value       = module.eks_alb_controller_iam.oidc_provider_arn
}

output "eks_aws_load_balancer_controller_role_arn" {
  description = "IRSA role ARN for AWS Load Balancer Controller (Helm serviceAccount)."
  value       = module.eks_alb_controller_iam.aws_load_balancer_controller_role_arn
}

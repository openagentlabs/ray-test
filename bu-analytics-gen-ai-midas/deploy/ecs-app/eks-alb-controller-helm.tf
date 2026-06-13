# -----------------------------------------------------------------------------
# Helm provider + AWS Load Balancer Controller helm_release.
#
# Authenticated to EKS the same way as the kubernetes provider
# (deploy/ecs-app/kubernetes-provider.tf): aws eks get-token exec plugin.
# The deployer role must be reachable from the Jenkins agent network
# (10.90.12.0/22 → TCP 443 already open on the EKS cluster security group).
#
# The controller is only installed when alb_nlb_enabled = true so it stays
# in sync with the ALB/NLB stack created by module.alb_nlb.
#
# IRSA role (midas-eks-dev-aws-load-balancer-controller) and OIDC provider
# are created by module.eks_alb_controller_iam (deploy/ecs-app/eks-alb-controller.tf).
# -----------------------------------------------------------------------------

provider "helm" {
  kubernetes {
    host                   = module.eks.eks_cluster_endpoint
    cluster_ca_certificate = base64decode(module.eks.eks_cluster_certificate_authority_data)

    exec {
      api_version = "client.authentication.k8s.io/v1beta1"
      command     = "aws"
      args = [
        "eks",
        "get-token",
        "--cluster-name", module.eks.eks_cluster_name,
        "--region", var.aws_region,
      ]
    }
  }
}

resource "helm_release" "aws_load_balancer_controller" {
  count = var.alb_nlb_enabled ? 1 : 0

  name             = "aws-load-balancer-controller"
  repository       = "https://aws.github.io/eks-charts"
  chart            = "aws-load-balancer-controller"
  version          = "1.8.1"
  namespace        = "kube-system"
  create_namespace = false

  # Do not block terraform apply waiting for pods to become Ready.
  # The controller is long-running; pod readiness is monitored separately
  # (kubectl rollout status in the Helm deploy stage). Without this,
  # Helm waits up to its default 5m timeout and terraform apply fails
  # with "context deadline exceeded" even when the upgrade succeeds.
  wait = false

  # Pull from private ECR mirror — the VPC has no internet egress (no NAT/IGW),
  # so public.ecr.aws is unreachable from nodes and causes ImagePullBackOff.
  # Image mirrored to private ECR by the ECR mirror pipeline before this runs.
  set {
    name  = "image.repository"
    value = "${var.aws_account_id}.dkr.ecr.${var.aws_region}.amazonaws.com/midas-${var.environment}-aws-load-balancer-controller"
  }

  set {
    name  = "clusterName"
    value = module.eks.eks_cluster_name
  }

  set {
    name  = "serviceAccount.create"
    value = "true"
  }

  # IRSA annotation so the controller pod assumes the pre-created IAM role
  # (midas-eks-dev-aws-load-balancer-controller) via projected service account token.
  set {
    name  = "serviceAccount.annotations.eks\\.amazonaws\\.com/role-arn"
    value = module.eks_alb_controller_iam.aws_load_balancer_controller_role_arn
  }

  set {
    name  = "region"
    value = var.aws_region
  }

  set {
    name  = "vpcId"
    value = var.eks_vpc_id
  }

  # Register pod IPs directly (no node-port indirection); matches target_type=ip
  # on the Terraform-managed ALB target groups (deploy/ecs-app/modules/alb-nlb/main.tf).
  set {
    name  = "defaultTargetType"
    value = "ip"
  }

  depends_on = [
    module.eks,
    module.eks_alb_controller_iam,
  ]
}

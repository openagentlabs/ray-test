resource "helm_release" "aws_load_balancer_controller" {
  provider = helm.eks

  name             = "aws-load-balancer-controller"
  repository       = "https://aws.github.io/eks-charts"
  chart            = "aws-load-balancer-controller"
  version          = var.chart_version
  namespace        = "kube-system"
  create_namespace = false
  wait             = true
  timeout          = 600

  values = [
    yamlencode({
      clusterName = var.cluster_name
      region      = var.solution.region
      vpcId       = var.vpc_id

      # Required for EKS Fargate — register pod IPs directly with target groups.
      defaultTargetType = "ip"

      serviceAccount = {
        create = true
        name   = local.service_account_name
        annotations = {
          "eks.amazonaws.com/role-arn" = aws_iam_role.alb_controller.arn
        }
      }

      createIngressClassResource = true
      ingressClass               = var.ingress_class
      ingressClassParams = {
        create = true
        name   = var.ingress_class
        spec = {
          scheme        = "internet-facing"
          ipAddressType = "ipv4"
          # Do not set group.name here — each Ingress declares
          # alb.ingress.kubernetes.io/group.name (arb-public, arb-ray).
        }
      }

      resources = {
        limits = {
          cpu    = "200m"
          memory = "500Mi"
        }
        requests = {
          cpu    = "100m"
          memory = "200Mi"
        }
      }

      enableShield = false
      enableWaf    = false
      enableWafv2  = false
    }),
  ]

  depends_on = [
    aws_iam_role_policy_attachment.alb_controller,
  ]
}

##################################################
#     We want to distinguish ALBs being defined
#     per environment
##################################################


##################################
#     NLB Definitions
##################################
resource "aws_lb" "exlerate_ai_gateway_nlb" {
  name                       = "${var.eks_cluster_name}-nlb-litellm"
  internal                   = true
  load_balancer_type         = "network"
  subnets                    = var.alb_subnets
  security_groups            = [aws_security_group.exlerate_litellm_alb_sg.id]
  enable_deletion_protection = true
}

resource "aws_lb" "exlerate_ai_gateway_langfuse_nlb" {
  name                       = "${var.eks_cluster_name}-nlb-langfuse"
  internal                   = true
  load_balancer_type         = "network"
  subnets                    = var.alb_subnets
  security_groups            = [aws_security_group.exlerate_langfuse_alb_sg.id]
  enable_deletion_protection = true
}

# ALB Permission sets and secret defintions
module "alb_irsa_permissions_set" {
  source           = "./irsa_blocks"
  eks_cluster_name = var.eks_cluster_name
  application      = "${var.eks_cluster_name}-alb"

  eks_oidc_url       = local.eks_oidc_url # This only changes if the cluster is redeployed
  eks_namespace      = "kube-system"
  account_id         = data.aws_caller_identity.current.account_id
  irsa_account_name  = var.alb_irsa_account_name
  image_pull_secrets = ["jfrog-regcred"]
  policy_arns = [
    aws_iam_policy.alb_controller_policy.arn
  ]

  depends_on = [aws_eks_cluster.exlerate_eks_cluster]
}

##################################
#    ALB Controller
##################################
resource "kubernetes_cluster_role_v1" "alb_ingress_controller" {
  count = local.current.enable_lb ? 1 : 0
  metadata {
    name = var.alb_irsa_account_name

    labels = {
      "app.kubernetes.io/name" = var.alb_irsa_account_name
    }
  }

  rule {
    api_groups = [
      "",
      "extensions"
    ]

    resources = [
      "configmaps",
      "endpoints",
      "events",
      "ingresses",
      "ingresses/status",
      "services",
      "pods/status"
    ]

    verbs = [
      "create",
      "get",
      "list",
      "update",
      "watch",
      "patch"
    ]
  }

  rule {
    api_groups = [
      "",
      "extensions"
    ]

    resources = [
      "nodes",
      "pods",
      "secrets",
      "services",
      "namespaces"
    ]

    verbs = [
      "get",
      "list",
      "watch"
    ]
  }
}

resource "kubernetes_cluster_role_binding_v1" "alb_ingress_controller" {
  count = local.current.enable_lb ? 1 : 0
  metadata {
    name = var.alb_irsa_account_name

    labels = {
      "app.kubernetes.io/name" = var.alb_irsa_account_name
    }
  }

  subject {
    kind      = "ServiceAccount"
    name      = var.alb_irsa_account_name
    namespace = "kube-system"
  }

  role_ref {
    api_group = "rbac.authorization.k8s.io"
    kind      = "ClusterRole"
    name      = var.alb_irsa_account_name
  }
}

locals {
  use_import = var.environment == "qa" || var.environment == "dev-stable"
  jfrog_regcred = jsondecode(
    local.use_import ? data.aws_secretsmanager_secret_version.jfrog_regcred_import[0].secret_string :
  data.aws_secretsmanager_secret_version.jfrog_regcred[0].secret_string)
}

resource "kubernetes_secret_v1" "jfrog_regcred" {
  metadata {
    name      = "jfrog-regcred"
    namespace = "kube-system"
  }

  type = "kubernetes.io/dockerconfigjson"

  data = {
    ".dockerconfigjson" = jsonencode({
      auths = {
        (local.jfrog_regcred.server) = {
          "username" = local.jfrog_regcred.username
          "password" = local.jfrog_regcred.password
          "email"    = local.jfrog_regcred.email
          "auth"     = base64encode("${local.jfrog_regcred.username}:${local.jfrog_regcred.password}")
        }
      }
    })
  }
}

# This application is what dynamically provisions ALBs for applications
resource "helm_release" "aws_alb_controller" {
  count = local.current.enable_lb ? 1 : 0
  name  = "aws-load-balancer-controller"

  chart      = "aws-load-balancer-controller"
  repository = "https://aws.github.io/eks-charts"
  version    = var.aws_load_balancer_controller_chart_version

  namespace = "kube-system"

  # MIDAS: bump from default 300s. Brand-new EKS nodes can take 5-7 min to pull the
  # controller image (cold cache, no in-region pull-through), generate the webhook
  # cert (cert-manager hook), pass leader election, and pass the readiness probe. The
  # default 300s caused build #15 + #17 to fail at exactly 5m elapsed even though the
  # release was actually progressing. cleanup_on_fail rolls back partial installs so
  # the next apply doesn't trip "name already in use".
  timeout         = 900
  wait            = true
  cleanup_on_fail = true

  set = concat(
    [
      {
        name  = "vpcId"
        value = var.vpc_id
      },
      {
        name  = "clusterName"
        value = var.eks_cluster_name
      },
      {
        name  = "serviceAccount.create"
        value = false
      },
      {
        # MIDAS bug-fix: the helm release MUST use the SAME service-account name
        # that module.alb_irsa_permissions_set creates (which is
        # var.alb_irsa_account_name, e.g. "midas-aigtw-dev-alb-ingress-controller").
        # Upstream hardcoded "${var.eks_cluster_name}-alb-ingress-controller"
        # which expanded to "midas-eks-aigtw-dev-alb-ingress-controller" — a
        # different name, so the ReplicaSet got `error looking up service account
        # ... not found` and never created any pods. The helm release then sat
        # waiting for readiness and timed out (build #15, #17, #18 all hit this).
        name  = "serviceAccount.name"
        value = var.alb_irsa_account_name
      },
      {
        # MIDAS in-tree fork: image now pulled from MIDAS ECR via IRSA, not JFrog.
        name  = "image.repository"
        value = var.aws_load_balancer_controller_image_repo
      },
      {
        name  = "image.tag"
        value = var.aws_load_balancer_controller_image_tag
      }
    ],
    var.use_jfrog_image_pull_secret ? [
      {
        name  = "imagePullSecrets[0].name"
        value = "jfrog-regcred"
      }
    ] : []
  )

  depends_on = [
    module.alb_irsa_permissions_set.irsa_sa
  ]
}

#########################
#   LiteLLM  ALB Config #
#########################
data "aws_lb" "litellm_alb" {
  count = var.bootstrap_phase >= 2 ? 1 : 0
  tags = {
    "elbv2.k8s.aws/cluster"    = "${var.eks_cluster_name}"
    "ingress.k8s.aws/resource" = "LoadBalancer"
    # Live tag value confirmed via aws elbv2 describe-tags: "midas-aigtw-litellm"
    # (ALB controller derives this from the Ingress group.name / stack annotation).
    "ingress.k8s.aws/stack"    = "midas-aigtw-litellm"
  }
}

# Only one ALB is allowed as target
resource "aws_lb_target_group" "nlb_to_alb" {
  count       = var.bootstrap_phase >= 2 ? 1 : 0
  name        = "${var.eks_cluster_name}-nlb-tg-443"
  port        = 443
  protocol    = "TCP"
  vpc_id      = aws_lb.exlerate_ai_gateway_nlb.vpc_id
  target_type = "alb"
  health_check {
    enabled             = true
    unhealthy_threshold = 3
    # NLB probes the ALB IP directly without a Host header so the ALB's
    # host-based routing rule never matches and the default fixed-response
    # fires (404). Accepting 200-404 confirms the ALB is reachable and
    # serving TLS without requiring a routable Host header on the probe.
    path                = "/"
    port                = "traffic-port"
    timeout             = 120
    interval            = 180
    healthy_threshold   = 3
    protocol            = "HTTPS"
    matcher             = "200-404"
  }
}

# Register the ALB as the only target.
# Gated on bootstrap_phase >= 3: the LiteLLM ALB must have a 443 listener before
# AWS allows registering it as an ALB-type target on port 443. That listener is
# created by the ALB ingress controller when ORD5 (LiteLLM Helm) deploys the Ingress
# with HTTPS. Run ORD1 at phase 2 first, then ORD5, then re-run ORD1 at phase 3.
#
# AWS requirement for target_type=alb: only target_group_arn + target_id are valid.
# Neither port nor availability_zone may be specified (both raise ValidationError).
resource "aws_lb_target_group_attachment" "nlb_to_alb" {
  count            = var.bootstrap_phase >= 3 ? 1 : 0
  target_group_arn = aws_lb_target_group.nlb_to_alb[0].arn
  target_id        = data.aws_lb.litellm_alb[0].arn
  # AWS: target_type=alb forbids BOTH port and availability_zone overrides.
  # Only target_group_arn + target_id are valid for ALB-type attachments.
}

# # Wire NLB listener to that TG
resource "aws_lb_listener" "nlb_443" {
  count             = var.bootstrap_phase >= 2 ? 1 : 0
  load_balancer_arn = aws_lb.exlerate_ai_gateway_nlb.arn
  port              = 443
  protocol          = "TCP"
  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.nlb_to_alb[0].arn
  }
  depends_on = [aws_lb_target_group.nlb_to_alb]
}

#########################
#   Langfuse  ALB Config #
#########################
data "aws_lb" "langfuse_alb" {
  count = var.bootstrap_phase >= 2 ? 1 : 0
  tags = {
    "elbv2.k8s.aws/cluster"    = "${var.eks_cluster_name}"
    "ingress.k8s.aws/resource" = "LoadBalancer"
    # Live tag value confirmed via aws elbv2 describe-tags: "midas-aigtw-langfuse"
    "ingress.k8s.aws/stack"    = "midas-aigtw-langfuse"
  }
}

# Only one ALB is allowed as target.
# MIDAS in-tree fork: shortened name from "${cluster}-lanfuse-nlb-tg-443" (38 chars,
# exceeds AWS TG name limit of 32) to "${cluster}-lf-tg443" (28 chars).
resource "aws_lb_target_group" "langfuse_nlb_to_alb" {
  count       = var.bootstrap_phase >= 2 ? 1 : 0
  name        = "${var.eks_cluster_name}-lf-tg443"
  port        = 443
  protocol    = "TCP"
  vpc_id      = aws_lb.exlerate_ai_gateway_langfuse_nlb.vpc_id
  target_type = "alb"
  health_check {
    enabled             = true
    unhealthy_threshold = 3
    # NLB probes the ALB IP without a Host header; the ALB host-based rule
    # never matches so the default fixed-response fires (404). Accepting
    # 200-404 confirms the ALB is reachable without needing a routable Host.
    path                = "/"
    port                = "traffic-port"
    timeout             = 120
    interval            = 180
    healthy_threshold   = 3
    protocol            = "HTTPS"
    matcher             = "200-404"
  }
}

# Register the ALB as the only target.
# Gated on bootstrap_phase >= 3: the Langfuse ALB must have a 443 listener before
# AWS allows registering it as an ALB-type target on port 443. That listener is
# created by the ALB ingress controller when ORD4 (Langfuse Helm) deploys the Ingress
# with HTTPS. Run ORD1 at phase 2 first, then ORD4, then re-run ORD1 at phase 3.
#
# AWS: ALB targets require AvailabilityZone=all on RegisterTargets.
resource "aws_lb_target_group_attachment" "langfuse_nlb_to_alb" {
  count            = var.bootstrap_phase >= 3 ? 1 : 0
  target_group_arn = aws_lb_target_group.langfuse_nlb_to_alb[0].arn
  target_id        = data.aws_lb.langfuse_alb[0].arn
  # AWS: target_type=alb forbids BOTH port and availability_zone overrides.
}

# # Wire NLB listener to that TG
resource "aws_lb_listener" "langfuse_nlb_443" {
  count             = var.bootstrap_phase >= 2 ? 1 : 0
  load_balancer_arn = aws_lb.exlerate_ai_gateway_langfuse_nlb.arn
  port              = 443
  protocol          = "TCP"
  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.langfuse_nlb_to_alb[0].arn
  }
  depends_on = [aws_lb_target_group.langfuse_nlb_to_alb]
}

#############################
#   Control-API NLB Config  #
#############################
resource "aws_lb" "exlerate_ai_gateway_c1_api_nlb" {
  name                       = "${var.eks_cluster_name}-nlb-c1-api"
  internal                   = true
  load_balancer_type         = "network"
  subnets                    = var.alb_subnets
  security_groups            = [aws_security_group.exlerate_c1_api_alb_sg.id]
  enable_deletion_protection = true
}

data "aws_lb" "c1_api_alb" {
  count = var.bootstrap_phase >= 2 ? 1 : 0
  tags = {
    "elbv2.k8s.aws/cluster"    = "${var.eks_cluster_name}"
    "ingress.k8s.aws/resource" = "LoadBalancer"
    # Live tag value confirmed via aws elbv2 describe-tags: "midas-aigtw-c1-api"
    "ingress.k8s.aws/stack"    = "midas-aigtw-c1-api"
  }
}

resource "aws_lb_target_group" "c1_api_nlb_to_alb" {
  count       = var.bootstrap_phase >= 2 ? 1 : 0
  # MIDAS: original name "${var.eks_cluster_name}-c1-api-nlb-tg-443" is 37 chars (AWS limit=32).
  # Shortened to "${var.eks_cluster_name}-c1-tg443" = 28 chars.
  name        = "${var.eks_cluster_name}-c1-tg443"
  port        = 443
  protocol    = "TCP"
  vpc_id      = aws_lb.exlerate_ai_gateway_c1_api_nlb.vpc_id
  target_type = "alb"
  health_check {
    enabled             = true
    unhealthy_threshold = 3
    # NLB probes the ALB IP without a Host header; the ALB host-based rule
    # never matches so the default fixed-response fires (404). Accepting
    # 200-404 confirms the ALB is reachable without needing a routable Host.
    path                = "/"
    port                = "traffic-port"
    timeout             = 120
    interval            = 180
    healthy_threshold   = 3
    protocol            = "HTTPS"
    matcher             = "200-404"
  }
}

resource "aws_lb_target_group_attachment" "c1_api_nlb_to_alb" {
  count            = var.bootstrap_phase >= 2 ? 1 : 0
  target_group_arn = aws_lb_target_group.c1_api_nlb_to_alb[0].arn
  target_id        = data.aws_lb.c1_api_alb[0].arn
  # AWS: target_type=alb forbids BOTH port and availability_zone overrides.
}

resource "aws_lb_listener" "c1_api_nlb_443" {
  count             = var.bootstrap_phase >= 2 ? 1 : 0
  load_balancer_arn = aws_lb.exlerate_ai_gateway_c1_api_nlb.arn
  port              = 443
  protocol          = "TCP"
  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.c1_api_nlb_to_alb[0].arn
  }
  depends_on = [aws_lb_target_group.c1_api_nlb_to_alb]
}

##################################
#   NLB DNS Name Outputs
##################################
output "litellm_nlb_dns_name" {
  description = "DNS name of the LiteLLM NLB"
  value       = aws_lb.exlerate_ai_gateway_nlb.dns_name
}

output "langfuse_nlb_dns_name" {
  description = "DNS name of the Langfuse NLB"
  value       = aws_lb.exlerate_ai_gateway_langfuse_nlb.dns_name
}

output "c1_api_nlb_dns_name" {
  description = "DNS name of the Control-API NLB"
  value       = aws_lb.exlerate_ai_gateway_c1_api_nlb.dns_name
}

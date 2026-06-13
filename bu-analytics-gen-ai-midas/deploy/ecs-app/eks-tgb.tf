# -----------------------------------------------------------------------------
# TargetGroupBinding resources — wires the Terraform-managed ALB target groups
# to the Kubernetes Services so the AWS Load Balancer Controller automatically
# keeps pod IPs registered/deregistered as pods are added or removed.
#
# How it works:
#   1. Terraform creates ALB target groups (modules/alb-nlb/main.tf, target_type=ip).
#   2. helm_release.aws_load_balancer_controller installs the controller
#      (deploy/ecs-app/eks-alb-controller-helm.tf).
#   3. These kubernetes_manifest resources create TargetGroupBinding CRDs.
#   4. The controller watches each TGB's referenced Service Endpoints and calls
#      RegisterTargets / DeregisterTargets automatically — no manual steps.
#
# Only created when alb_nlb_enabled = true (same gate as module.alb_nlb).
# depends_on helm_release ensures the elbv2.k8s.aws/v1beta1 CRD exists before apply.
# -----------------------------------------------------------------------------

locals {
  tgb_specs = var.alb_nlb_enabled ? {
    frontend = {
      name    = "midas-frontend-tgb"
      service = "midas-web-frontend-svc"
      port    = 8080
      tg_arn  = module.alb_nlb[0].alb_frontend_target_group_arn
    }
    backend = {
      name    = "midas-backend-tgb"
      service = "envoy-router"
      port    = 80
      tg_arn  = module.alb_nlb[0].alb_backend_target_group_arn
    }
    graph = {
      name    = "midas-graph-tgb"
      service = "midas-graph-svc"
      port    = 8001
      tg_arn  = module.alb_nlb[0].alb_graph_target_group_arn
    }
  } : {}
}

resource "kubernetes_manifest" "tgb" {
  for_each = local.tgb_specs

  manifest = {
    apiVersion = "elbv2.k8s.aws/v1beta1"
    kind       = "TargetGroupBinding"
    metadata = {
      name      = each.value.name
      namespace = "midas-apps"
    }
    spec = {
      serviceRef = {
        name = each.value.service
        port = each.value.port
      }
      targetGroupARN = each.value.tg_arn
      targetType     = "ip"
    }
  }

  # Controller CRD must exist before kubernetes_manifest can be planned/applied.
  depends_on = [
    helm_release.aws_load_balancer_controller,
  ]
}

# -----------------------------------------------------------------------------
# EKS cluster security group ingress rules for ALB → pod traffic.
# Only created when alb_nlb_enabled = true.
#
# Design choice (decoupling the ALB SG from the EKS cluster SG):
#
#   The AWS Load Balancer Controller with target_type=ip sends traffic from
#   ALB ENIs (in the ALB subnets) to pod ENIs (in the cluster SG). The pod
#   side therefore MUST allow inbound on 8080/10000/8001, but the source does
#   NOT have to be the ALB SG — it only has to cover the ALB ENI CIDRs.
#
#   Using `source_security_group_id = module.alb_nlb[0].alb_sg_id` couples
#   the EKS cluster SG to the ALB SG. AWS then refuses to delete the ALB SG
#   while these rules exist on the cluster SG (DependencyViolation), which
#   caused multi-minute destroy hangs during ALB/NLB replace cycles.
#
#   Instead, source these rules from the ALB subnet CIDRs. The cluster SG
#   stops referencing the ALB SG entirely, so the ALB SG can be created and
#   destroyed independently of the cluster SG. The cluster SG itself is
#   managed by AWS EKS and is never destroyed by this Terraform.
#
#   Using `aws_vpc_security_group_ingress_rule` (one rule per resource)
#   instead of the legacy `aws_security_group_rule` gives clean, per-rule
#   create/destroy with no shared-rule race conditions.
# -----------------------------------------------------------------------------

data "aws_subnet" "alb" {
  for_each = var.alb_nlb_enabled ? toset(var.alb_subnet_ids) : toset([])
  id       = each.value
}

locals {
  # Flat (cidr, port) pairs so each rule is a separate resource.
  # 443 is included so the NLB→ALB→pod path works end-to-end on HTTPS
  # (ALB subnet CIDRs must be able to reach pod ENIs on 443 when TLS pass-through is used).
  alb_to_pod_ports = var.alb_nlb_enabled ? [443, 8080, 10000, 8001] : []

  alb_to_pod_rules = var.alb_nlb_enabled ? {
    for pair in flatten([
      for port in local.alb_to_pod_ports : [
        for subnet_id, subnet in data.aws_subnet.alb : {
          key  = "${port}-${subnet_id}"
          port = port
          cidr = subnet.cidr_block
        }
      ]
    ]) : pair.key => pair
  } : {}
}

resource "aws_vpc_security_group_ingress_rule" "eks_from_alb_subnet_cidrs" {
  for_each = local.alb_to_pod_rules

  security_group_id = module.eks.eks_cluster_security_group_id
  description       = "TCP ${each.value.port} from ALB subnet ${each.value.cidr} to EKS pods"
  ip_protocol       = "tcp"
  from_port         = each.value.port
  to_port           = each.value.port
  cidr_ipv4         = each.value.cidr

  tags = {
    Name        = "midas-${var.environment}-eks-from-alb-subnet-${each.value.port}"
    Environment = var.environment
    ManagedBy   = "terraform"
    Project     = "midas-alb-nlb"
  }
}

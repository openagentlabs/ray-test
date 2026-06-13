# Private NLB (static IPs) in front of a private ALB (stable DNS) for MIDAS EKS services.
#
# ---------------------------------------------------------------------------
# Traffic flow:
#
#   When certificate_arn is set (HTTPS mode — production target):
#     Corporate / Jumpbox → NLB TCP:443 → ALB HTTPS:443 (TLS terminates here)
#                                       → frontend pods HTTP:8080
#                                       → envoy pods HTTP:10000
#                                       → graph    pods HTTP:8001
#
#   When certificate_arn is empty (no-listener mode):
#     NLB and ALB are created but have no listeners. The infrastructure is
#     ready; TGBs register pod IPs. Add certificate_arn to activate HTTPS.
#
#   All SG rules, listeners, TGs, and NLB attachments are gated on
#   cert_ready (certificate_arn != "") so Terraform does not error when
#   the ACM certificate has not yet been provisioned.
#
#   ALB listener rules strip path prefix via url-rewrite transform:
#     /automate  or /automate/*  → frontend pods :8080
#     /backend   or /backend/*   → envoy pods    :10000
#     /graph     or /graph/*     → graph pods    :8001
#     default                    → frontend pods :8080
#
# Requires AWS provider >= 6.19.0 for aws_lb_listener_rule transform/url-rewrite.
# ---------------------------------------------------------------------------

locals {
  name_prefix = "midas-${var.environment}"
  cert_ready  = var.certificate_arn != ""

  # Corporate URL + direct ALB DNS (ops/jump) both match so path-prefixed routes work in either case.
  path_rule_host_header_values = var.public_https_hostname != "" ? [var.public_https_hostname, aws_lb.alb.dns_name] : []

  common_tags = {
    Environment = var.environment
    ManagedBy   = "Terraform"
    AccountId   = var.aws_account_id
    Project     = "midas-alb-nlb"
  }
}

# ---------------------------------------------------------------------------
# Security Groups
# ---------------------------------------------------------------------------

# NLB SG: accepts TCP 443 from corporate CIDRs and jumpbox; egresses TCP 443 to ALB only.
#
# Uses name_prefix + create_before_destroy so Terraform can replace the SG
# cleanly when an attribute that forces replacement changes (e.g. `description`,
# `name`, `vpc_id`). AWS does not support in-place updates of those fields, so a
# plain `name =` + default destroy-then-create lifecycle causes Terraform to
# delete the SG *before* the attached NLB (`aws_lb.nlb`) is rewired to the new
# SG. EC2 then rejects the DeleteSecurityGroup call with DependencyViolation
# and the apply hangs for ~15 minutes. With the settings below Terraform
# creates the replacement SG first (unique name thanks to name_prefix), updates
# the NLB's security_groups attribute in-place to point at the new SG, and then
# removes the old one. See also alb-nlb-eks-sg.tf for the sibling DependencyViolation
# mitigation that decouples the EKS cluster SG from the ALB SG.
resource "aws_security_group" "nlb" {
  name_prefix = "${local.name_prefix}-nlb-sg-"
  description = "MIDAS private NLB - TCP 443 from corporate CIDRs and jumpbox; egress TCP 443 to ALB only"
  vpc_id      = var.vpc_id

  tags = merge(local.common_tags, { Name = "${local.name_prefix}-nlb-sg" })

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_vpc_security_group_ingress_rule" "nlb_from_corporate" {
  for_each = local.cert_ready ? toset(var.nlb_corporate_ingress_cidrs) : toset([])

  security_group_id = aws_security_group.nlb.id
  description       = "TCP 443 from corporate/TGW CIDR ${each.value}"
  ip_protocol       = "tcp"
  from_port         = 443
  to_port           = 443
  cidr_ipv4         = each.value

  tags = merge(local.common_tags, { Name = "${local.name_prefix}-nlb-ingress-corporate-443" })
}

resource "aws_vpc_security_group_ingress_rule" "nlb_from_jumpbox" {
  count = local.cert_ready ? 1 : 0

  security_group_id            = aws_security_group.nlb.id
  description                  = "TCP 443 from SSM jumpbox for HTTPS testing"
  ip_protocol                  = "tcp"
  from_port                    = 443
  to_port                      = 443
  referenced_security_group_id = var.jumpbox_security_group_id

  tags = merge(local.common_tags, { Name = "${local.name_prefix}-nlb-ingress-jumpbox-443" })
}

resource "aws_vpc_security_group_ingress_rule" "nlb_from_jumpbox_secondary" {
  count = local.cert_ready && var.jumpbox_secondary_ingress_enabled ? 1 : 0

  security_group_id            = aws_security_group.nlb.id
  description                  = "TCP 443 from second SSM Linux jumpbox for HTTPS testing"
  ip_protocol                  = "tcp"
  from_port                    = 443
  to_port                      = 443
  referenced_security_group_id = var.jumpbox_security_group_id_secondary

  tags = merge(local.common_tags, { Name = "${local.name_prefix}-nlb-ingress-jumpbox-linux-secondary-443" })
}

resource "aws_vpc_security_group_ingress_rule" "nlb_from_jumpbox_windows" {
  count = local.cert_ready && var.jumpbox_windows_security_group_id != "" ? 1 : 0

  security_group_id            = aws_security_group.nlb.id
  description                  = "TCP 443 from Windows SSM test instance for HTTPS testing"
  ip_protocol                  = "tcp"
  from_port                    = 443
  to_port                      = 443
  referenced_security_group_id = var.jumpbox_windows_security_group_id

  tags = merge(local.common_tags, { Name = "${local.name_prefix}-nlb-ingress-jumpbox-windows-443" })
}

resource "aws_vpc_security_group_egress_rule" "nlb_to_alb" {
  count = local.cert_ready ? 1 : 0

  security_group_id            = aws_security_group.nlb.id
  description                  = "TCP 443 to ALB (NLB target_type=alb HTTPS forwarding)"
  ip_protocol                  = "tcp"
  from_port                    = 443
  to_port                      = 443
  referenced_security_group_id = aws_security_group.alb.id

  tags = merge(local.common_tags, { Name = "${local.name_prefix}-nlb-egress-alb-443" })
}

# ALB SG: accepts TCP 443 from NLB and jumpbox; egresses HTTP to pods on their container ports.
#
# Same name_prefix + create_before_destroy rationale as aws_security_group.nlb
# above: the ALB SG is attached to `aws_lb.alb`, so replacing it with the
# default destroy-then-create lifecycle would hit DependencyViolation.
resource "aws_security_group" "alb" {
  name_prefix = "${local.name_prefix}-alb-sg-"
  description = "MIDAS private ALB - TCP 443 from NLB and jumpbox; egress HTTP to EKS pods (8080/10000/8001)"
  vpc_id      = var.vpc_id

  tags = merge(local.common_tags, { Name = "${local.name_prefix}-alb-sg" })

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_vpc_security_group_ingress_rule" "alb_from_nlb" {
  count = local.cert_ready ? 1 : 0

  security_group_id            = aws_security_group.alb.id
  description                  = "TCP 443 from NLB (forwarded HTTPS corporate traffic)"
  ip_protocol                  = "tcp"
  from_port                    = 443
  to_port                      = 443
  referenced_security_group_id = aws_security_group.nlb.id

  tags = merge(local.common_tags, { Name = "${local.name_prefix}-alb-ingress-nlb-443" })
}

resource "aws_vpc_security_group_ingress_rule" "alb_from_jumpbox" {
  count = local.cert_ready ? 1 : 0

  security_group_id            = aws_security_group.alb.id
  description                  = "TCP 443 from SSM jumpbox for direct ALB HTTPS testing"
  ip_protocol                  = "tcp"
  from_port                    = 443
  to_port                      = 443
  referenced_security_group_id = var.jumpbox_security_group_id

  tags = merge(local.common_tags, { Name = "${local.name_prefix}-alb-ingress-jumpbox-443" })
}

resource "aws_vpc_security_group_ingress_rule" "alb_from_jumpbox_secondary" {
  count = local.cert_ready && var.jumpbox_secondary_ingress_enabled ? 1 : 0

  security_group_id            = aws_security_group.alb.id
  description                  = "TCP 443 from second SSM Linux jumpbox for direct ALB HTTPS testing"
  ip_protocol                  = "tcp"
  from_port                    = 443
  to_port                      = 443
  referenced_security_group_id = var.jumpbox_security_group_id_secondary

  tags = merge(local.common_tags, { Name = "${local.name_prefix}-alb-ingress-jumpbox-linux-secondary-443" })
}

resource "aws_vpc_security_group_ingress_rule" "alb_from_jumpbox_windows" {
  count = local.cert_ready && var.jumpbox_windows_security_group_id != "" ? 1 : 0

  security_group_id            = aws_security_group.alb.id
  description                  = "TCP 443 from Windows SSM test instance for direct ALB HTTPS testing"
  ip_protocol                  = "tcp"
  from_port                    = 443
  to_port                      = 443
  referenced_security_group_id = var.jumpbox_windows_security_group_id

  tags = merge(local.common_tags, { Name = "${local.name_prefix}-alb-ingress-jumpbox-windows-443" })
}

# ALB egress to pods: plain HTTP on container ports (TLS terminates at ALB).
# Rules use the VPC CIDR rather than a cross-SG reference to the EKS cluster SG.
# Cross-SG references cause DependencyViolation when Terraform tries to replace
# the ALB SG: EC2 refuses to delete the old SG while it is still referenced by
# another SG's rule. Using a CIDR breaks that coupling entirely.
resource "aws_vpc_security_group_egress_rule" "alb_to_pods_8080" {
  count = local.cert_ready ? 1 : 0

  security_group_id = aws_security_group.alb.id
  description       = "HTTP 8080 to EKS pods (frontend) via VPC CIDR"
  ip_protocol       = "tcp"
  from_port         = 8080
  to_port           = 8080
  cidr_ipv4         = var.vpc_cidr

  tags = merge(local.common_tags, { Name = "${local.name_prefix}-alb-egress-pods-8080" })
}

resource "aws_vpc_security_group_egress_rule" "alb_to_pods_10000" {
  count = local.cert_ready ? 1 : 0

  security_group_id = aws_security_group.alb.id
  description       = "HTTP 10000 to EKS pods (envoy traffic) via VPC CIDR"
  ip_protocol       = "tcp"
  from_port         = 10000
  to_port           = 10000
  cidr_ipv4         = var.vpc_cidr

  tags = merge(local.common_tags, { Name = "${local.name_prefix}-alb-egress-pods-10000" })
}

resource "aws_vpc_security_group_egress_rule" "alb_to_pods_8001" {
  count = local.cert_ready ? 1 : 0

  security_group_id = aws_security_group.alb.id
  description       = "HTTP 8001 to EKS pods (graph) via VPC CIDR"
  ip_protocol       = "tcp"
  from_port         = 8001
  to_port           = 8001
  cidr_ipv4         = var.vpc_cidr

  tags = merge(local.common_tags, { Name = "${local.name_prefix}-alb-egress-pods-8001" })
}

# ---------------------------------------------------------------------------
# ALB Target Groups — target_type=ip; plain HTTP to pods.
# AWS LB Controller TargetGroupBinding manages pod IP registration via
# Kubernetes Endpoints automatically on every rollout.
# Health checks use permissive 200-499 matcher for initial setup; tighten
# to service-specific paths once services are confirmed healthy.
#
# AWS does not allow disabling health checks for ALB target groups with
# target_type=ip. We use the maximum API-allowed interval (300s), maximum
# timeout (120s, strictly less than interval), minimum healthy threshold (2),
# and maximum unhealthy threshold (10) so probes are least disruptive during
# long-running API work. NLB→ALB (target_type=alb) uses the same maxima where
# supported by the NLB target group API.
# ---------------------------------------------------------------------------

locals {
  # ALB → pod (IP): interval 5–300s, timeout 2–120s, timeout < interval
  alb_hc_interval            = 300
  alb_hc_timeout             = 120
  alb_hc_healthy_threshold   = 2
  alb_hc_unhealthy_threshold = 10

  # NLB → ALB (target_type=alb): interval up to 300s; timeout 6–120s per API
  nlb_hc_interval            = 300
  nlb_hc_timeout             = 120
  nlb_hc_healthy_threshold   = 2
  nlb_hc_unhealthy_threshold = 10
}

resource "aws_lb_target_group" "frontend" {
  name                 = "${local.name_prefix}-alb-fe-tg"
  port                 = 8080
  protocol             = "HTTP"
  vpc_id               = var.vpc_id
  target_type          = "ip"
  deregistration_delay = 30

  health_check {
    enabled             = true
    path                = "/"
    matcher             = "200-499"
    interval            = local.alb_hc_interval
    timeout             = local.alb_hc_timeout
    healthy_threshold   = local.alb_hc_healthy_threshold
    unhealthy_threshold = local.alb_hc_unhealthy_threshold
  }

  tags = merge(local.common_tags, { Name = "${local.name_prefix}-alb-fe-tg" })
}

# checkov:skip=CKV_AWS_378: ALB terminates TLS at the public-facing listener; pod-side HTTP is standard intra-VPC practice within vpc-0c4d673f3e95a93eb. Enabling HTTPS to pods requires per-pod TLS cert management (separate service-mesh workstream). Accepted risk per ADR 0010.
resource "aws_lb_target_group" "backend" {
  name                 = "${local.name_prefix}-alb-be-tg"
  port                 = 10000
  protocol             = "HTTP"
  vpc_id               = var.vpc_id
  target_type          = "ip"
  deregistration_delay = 30

  # lb_cookie stickiness remains enabled to keep backend path behavior stable
  # during the Envoy cutover. Set var.backend_target_group_stickiness_seconds
  # = 0 to disable.
  stickiness {
    type            = "lb_cookie"
    cookie_duration = var.backend_target_group_stickiness_seconds > 0 ? var.backend_target_group_stickiness_seconds : 86400
    enabled         = var.backend_target_group_stickiness_seconds > 0
  }

  health_check {
    enabled             = true
    path                = "/health"
    port                = "8080"
    matcher             = "200-499"
    interval            = local.alb_hc_interval
    timeout             = local.alb_hc_timeout
    healthy_threshold   = local.alb_hc_healthy_threshold
    unhealthy_threshold = local.alb_hc_unhealthy_threshold
  }

  tags = merge(local.common_tags, { Name = "${local.name_prefix}-alb-be-tg" })
}

# checkov:skip=CKV_AWS_378: ALB terminates TLS at the public-facing listener; pod-side HTTP is standard intra-VPC practice within vpc-0c4d673f3e95a93eb. Enabling HTTPS to pods requires per-pod TLS cert management (separate service-mesh workstream). Accepted risk per ADR 0010.
resource "aws_lb_target_group" "graph" {
  name                 = "${local.name_prefix}-alb-gr-tg"
  port                 = 8001
  protocol             = "HTTP"
  vpc_id               = var.vpc_id
  target_type          = "ip"
  deregistration_delay = 30

  health_check {
    enabled             = true
    path                = "/"
    matcher             = "200-499"
    interval            = local.alb_hc_interval
    timeout             = local.alb_hc_timeout
    healthy_threshold   = local.alb_hc_healthy_threshold
    unhealthy_threshold = local.alb_hc_unhealthy_threshold
  }

  tags = merge(local.common_tags, { Name = "${local.name_prefix}-alb-gr-tg" })
}

# ---------------------------------------------------------------------------
# Internal ALB — HTTPS:443, TLS terminates here.
# ---------------------------------------------------------------------------

resource "aws_lb" "alb" {
  name               = "${local.name_prefix}-alb"
  internal           = true
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = var.alb_subnet_ids

  # Fortify "Reduced ELB Availability": deletion protection on by default so a
  # stray `terraform destroy` or AWS-console delete cannot take the ALB down.
  # To rebuild the ALB intentionally, disable this manually first.
  enable_deletion_protection = var.deletion_protection
  drop_invalid_header_fields = true

  # Set to 3600 s (60 min) to match the Cognito access-token and internal JWT
  # lifetime. The previous 600 s limit was killing long-running AI/analysis
  # requests and forcing re-login mid-session. Long-lived idle connections are
  # not a concern here because the NLB in front keeps its own TCP keep-alive.
  idle_timeout = 3600

  tags = merge(local.common_tags, { Name = "${local.name_prefix}-alb" })
}

# HTTPS:443 listener — TLS terminates at the ALB using the ACM certificate.
# TLS 1.2+ and TLS 1.3 only; aligned with corporate security baseline.
# Only created when certificate_arn is provided.
resource "aws_lb_listener" "alb_https" {
  count = local.cert_ready ? 1 : 0

  load_balancer_arn = aws_lb.alb.arn
  port              = 443
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"
  certificate_arn   = var.certificate_arn

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.frontend.arn
  }

  tags = merge(local.common_tags, { Name = "${local.name_prefix}-alb-https-listener" })
}

# ---------------------------------------------------------------------------
# ALB listener rules with path prefix strip (url-rewrite transform).
# Requires AWS provider >= 6.19.0.
#
# When public_https_hostname is set, the path rules also require a matching
# Host (public FQDN or internal ALB DNS). Default forward for / is unchanged.
#
# The transform applies BEFORE the action so pods receive paths starting
# from "/" regardless of what prefix the client used.
# Regex captures everything after the prefix; empty capture produces "/".
# ---------------------------------------------------------------------------

resource "aws_lb_listener_rule" "frontend" {
  count = local.cert_ready ? 1 : 0

  listener_arn = aws_lb_listener.alb_https[0].arn
  priority     = 10

  dynamic "condition" {
    for_each = length(local.path_rule_host_header_values) > 0 ? [1] : []
    content {
      host_header {
        values = local.path_rule_host_header_values
      }
    }
  }

  condition {
    path_pattern {
      values = ["/automate", "/automate/*"]
    }
  }

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.frontend.arn
  }

  transform {
    type = "url-rewrite"
    url_rewrite_config {
      rewrite {
        regex   = "^/automate(?:/(.*))?$"
        replace = "/$1"
      }
    }
  }

  tags = merge(local.common_tags, { Name = "${local.name_prefix}-alb-rule-frontend" })
}

resource "aws_lb_listener_rule" "backend" {
  count = local.cert_ready ? 1 : 0

  listener_arn = aws_lb_listener.alb_https[0].arn
  priority     = 20

  dynamic "condition" {
    for_each = length(local.path_rule_host_header_values) > 0 ? [1] : []
    content {
      host_header {
        values = local.path_rule_host_header_values
      }
    }
  }

  condition {
    path_pattern {
      values = ["/backend", "/backend/*"]
    }
  }

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.backend.arn
  }

  transform {
    type = "url-rewrite"
    url_rewrite_config {
      rewrite {
        regex   = "^/backend(?:/(.*))?$"
        replace = "/$1"
      }
    }
  }

  tags = merge(local.common_tags, { Name = "${local.name_prefix}-alb-rule-backend" })
}

resource "aws_lb_listener_rule" "graph" {
  count = local.cert_ready ? 1 : 0

  listener_arn = aws_lb_listener.alb_https[0].arn
  priority     = 30

  dynamic "condition" {
    for_each = length(local.path_rule_host_header_values) > 0 ? [1] : []
    content {
      host_header {
        values = local.path_rule_host_header_values
      }
    }
  }

  condition {
    path_pattern {
      values = ["/graph", "/graph/*"]
    }
  }

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.graph.arn
  }

  transform {
    type = "url-rewrite"
    url_rewrite_config {
      rewrite {
        regex   = "^/graph(?:/(.*))?$"
        replace = "/$1"
      }
    }
  }

  tags = merge(local.common_tags, { Name = "${local.name_prefix}-alb-rule-graph" })
}

# ---------------------------------------------------------------------------
# Internal NLB — target_type=alb, TCP:443 → ALB HTTPS:443.
# One ENI per AZ = permanent static private IP per AZ.
# The NLB SG carries the corporate ingress rules; traffic flows to ALB SG.
# ---------------------------------------------------------------------------

resource "aws_lb" "nlb" {
  name               = "${local.name_prefix}-nlb"
  internal           = true
  load_balancer_type = "network"
  subnets            = var.nlb_subnet_ids
  security_groups    = [aws_security_group.nlb.id]

  # Fortify "Reduced ELB Availability": deletion protection on by default so a
  # stray `terraform destroy` or AWS-console delete cannot take the NLB down.
  # To rebuild the NLB intentionally, disable this manually first.
  enable_deletion_protection = var.deletion_protection

  tags = merge(local.common_tags, { Name = "${local.name_prefix}-nlb" })
}

# NLB target group pointing at the ALB on port 443.
# Health check uses HTTPS:443 because the ALB only exposes an HTTPS listener.
# Only created once the ALB HTTPS listener exists (cert_ready).
resource "aws_lb_target_group" "nlb_to_alb" {
  count = local.cert_ready ? 1 : 0

  name        = "${local.name_prefix}-nlb-alb-tg"
  port        = 443
  protocol    = "TCP"
  vpc_id      = var.vpc_id
  target_type = "alb"

  health_check {
    enabled             = true
    protocol            = "HTTPS"
    port                = "443"
    path                = "/"
    matcher             = "200-499"
    interval            = local.nlb_hc_interval
    timeout             = local.nlb_hc_timeout
    healthy_threshold   = local.nlb_hc_healthy_threshold
    unhealthy_threshold = local.nlb_hc_unhealthy_threshold
  }

  tags = merge(local.common_tags, { Name = "${local.name_prefix}-nlb-alb-tg" })
}

resource "aws_lb_target_group_attachment" "nlb_to_alb" {
  count = local.cert_ready ? 1 : 0

  target_group_arn = aws_lb_target_group.nlb_to_alb[0].arn
  target_id        = aws_lb.alb.arn
  port             = 443
  depends_on       = [aws_lb_listener.alb_https]
}

resource "aws_lb_listener" "nlb_tcp" {
  count = local.cert_ready ? 1 : 0

  load_balancer_arn = aws_lb.nlb.arn
  port              = 443
  protocol          = "TCP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.nlb_to_alb[0].arn
  }

  # Destroy ordering: this listener references nlb_to_alb. Without an edge to
  # aws_lb_target_group_attachment, Terraform can destroy the attachment and the
  # target group in parallel with the listener, causing ResourceInUse on
  # DeleteTargetGroup / long SG deletes. Listener depends on attachment => on
  # destroy the listener is removed first, releasing the TG from the NLB path.
  depends_on = [aws_lb_target_group_attachment.nlb_to_alb]

  tags = merge(local.common_tags, { Name = "${local.name_prefix}-nlb-tcp-443-listener" })
}

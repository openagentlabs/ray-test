# Internet-facing ALB — accept HTTP/HTTPS from allowed CIDRs; egress only to EKS workload SG
resource "aws_security_group" "alb" {
  name_prefix = "${local.name_prefix}-alb-"
  description = "Internet-facing ALB for ${var.cluster_name}"
  vpc_id      = var.vpc_id

  tags = {
    Name      = "${local.name_prefix}-alb"
    purpose   = "alb-public"
    Component = "network"
    Service   = "platform"
  }
}

resource "aws_vpc_security_group_ingress_rule" "alb_http" {
  for_each = toset(var.alb_ingress_cidr_blocks)

  security_group_id = aws_security_group.alb.id
  cidr_ipv4         = each.value
  from_port         = 80
  to_port           = 80
  ip_protocol       = "tcp"
  description       = "HTTP from ${each.value}"
}

resource "aws_vpc_security_group_ingress_rule" "alb_https" {
  for_each = toset(var.alb_ingress_cidr_blocks)

  security_group_id = aws_security_group.alb.id
  cidr_ipv4         = each.value
  from_port         = 443
  to_port           = 443
  ip_protocol       = "tcp"
  description       = "HTTPS from ${each.value}"
}

resource "aws_vpc_security_group_egress_rule" "alb_to_workloads" {
  for_each = toset([for port in var.workload_container_ports : tostring(port)])

  security_group_id            = aws_security_group.alb.id
  referenced_security_group_id = aws_security_group.eks_workloads.id
  from_port                    = tonumber(each.key)
  to_port                      = tonumber(each.key)
  ip_protocol                  = "tcp"
  description                  = "Forward to EKS workloads on port ${each.key}"
}

resource "aws_vpc_security_group_egress_rule" "alb_health_check" {
  security_group_id = aws_security_group.alb.id
  cidr_ipv4         = var.vpc_cidr_block
  from_port         = 1024
  to_port           = 65535
  ip_protocol       = "tcp"
  description       = "Health check return traffic within VPC"
}

# EKS cluster control plane — AWS-managed communication pattern
resource "aws_security_group" "eks_cluster" {
  name_prefix = "${local.name_prefix}-eks-cluster-"
  description = "EKS cluster control plane for ${var.cluster_name}"
  vpc_id      = var.vpc_id

  tags = {
    Name      = "${local.name_prefix}-eks-cluster"
    purpose   = "eks-control-plane"
    cluster   = var.cluster_name
    Component = "compute"
    Service   = "platform"
  }
}

resource "aws_vpc_security_group_ingress_rule" "eks_cluster_from_workloads" {
  security_group_id            = aws_security_group.eks_cluster.id
  referenced_security_group_id = aws_security_group.eks_workloads.id
  ip_protocol                  = "-1"
  description                  = "Cluster API from workload nodes/pods"
}

resource "aws_vpc_security_group_egress_rule" "eks_cluster_all" {
  security_group_id = aws_security_group.eks_cluster.id
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "-1"
  description       = "Cluster control plane egress"
}

# EKS Fargate workloads — ingress from ALB only on app ports; full egress for AWS APIs via NAT/endpoints
resource "aws_security_group" "eks_workloads" {
  name_prefix = "${local.name_prefix}-eks-workloads-"
  description = "EKS Fargate pod ENIs for ${var.cluster_name}"
  vpc_id      = var.vpc_id

  tags = {
    Name      = "${local.name_prefix}-eks-workloads"
    purpose   = "eks-fargate"
    cluster   = var.cluster_name
    Component = "compute"
    Service   = "platform"
  }
}

resource "aws_vpc_security_group_ingress_rule" "eks_workloads_from_alb" {
  for_each = toset([for port in var.workload_container_ports : tostring(port)])

  security_group_id            = aws_security_group.eks_workloads.id
  referenced_security_group_id = aws_security_group.alb.id
  from_port                    = tonumber(each.key)
  to_port                      = tonumber(each.key)
  ip_protocol                  = "tcp"
  description                  = "ALB to workload port ${each.key}"
}

resource "aws_vpc_security_group_ingress_rule" "eks_workloads_intra_vpc" {
  security_group_id = aws_security_group.eks_workloads.id
  cidr_ipv4         = var.vpc_cidr_block
  ip_protocol       = "-1"
  description       = "Intra-VPC service mesh / gRPC"
}

resource "aws_vpc_security_group_egress_rule" "eks_workloads_all" {
  security_group_id = aws_security_group.eks_workloads.id
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "-1"
  description       = "Workload egress (AWS APIs via VPC endpoints / NAT)"
}

# Bastion — no inbound by default (SSM Session Manager); optional SSH from trusted CIDRs
resource "aws_security_group" "bastion" {
  name_prefix = "${local.name_prefix}-bastion-"
  description = "Bastion host for ${var.cluster_name} (SSM preferred)"
  vpc_id      = var.vpc_id

  tags = {
    Name      = "${local.name_prefix}-bastion"
    purpose   = "bastion"
    Component = "network"
    Service   = "platform"
  }
}

resource "aws_vpc_security_group_ingress_rule" "bastion_ssh" {
  for_each = toset(var.bastion_ssh_cidr_blocks)

  security_group_id = aws_security_group.bastion.id
  cidr_ipv4         = each.value
  from_port         = 22
  to_port           = 22
  ip_protocol       = "tcp"
  description       = "SSH from ${each.value} (prefer SSM Session Manager)"
}

resource "aws_vpc_security_group_egress_rule" "bastion_https" {
  security_group_id = aws_security_group.bastion.id
  cidr_ipv4         = "0.0.0.0/0"
  from_port         = 443
  to_port           = 443
  ip_protocol       = "tcp"
  description       = "HTTPS for SSM and package updates"
}

resource "aws_vpc_security_group_egress_rule" "bastion_dns" {
  security_group_id = aws_security_group.bastion.id
  cidr_ipv4         = "0.0.0.0/0"
  from_port         = 53
  to_port           = 53
  ip_protocol       = "udp"
  description       = "DNS"
}

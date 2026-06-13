locals {
  karpenter_tags = { "karpenter.sh/discovery" = var.eks_cluster_name }

  # Pod ports the ALB/NLB needs to reach on the EKS-managed cluster SG.
  # The EKS-managed cluster SG (cluster_security_group_id) only has a self-all
  # rule by default. These rules open the inbound paths from the VPC CIDR so the
  # ALB (whose ENIs sit in the same VPC) can reach pods on their container ports.
  # Rules are added via aws_vpc_security_group_ingress_rule (one resource per
  # port/cidr pair) to avoid the shared-rule race conditions of the legacy
  # aws_security_group_rule resource.
  aigtw_eks_cluster_sg_ports = [443, 9001, 4000, 3000, 30369]
  aigtw_eks_cluster_sg_cidrs = [var.vpc_cidrs, "10.90.12.0/24"]

  aigtw_eks_cluster_sg_rules = {
    for pair in flatten([
      for port in local.aigtw_eks_cluster_sg_ports : [
        for cidr in local.aigtw_eks_cluster_sg_cidrs : {
          key  = "${port}-${cidr}"
          port = port
          cidr = cidr
        }
      ]
    ]) : pair.key => pair
  }
}

####################################
# EKS Cluster Security Group #
####################################

resource "aws_security_group" "exlerate_eks_cluster_sg" {
  name        = "exl-${var.eks_cluster_name}-sg"
  description = "Security Group defintions for litellm and Langfuse Clusters"
  vpc_id      = var.vpc_id

  dynamic "ingress" {
    for_each = local.ingress_rules_eks

    content {
      from_port        = ingress.value.from_port
      to_port          = ingress.value.to_port
      protocol         = ingress.value.protocol
      self             = lookup(ingress.value, "self", false)
      cidr_blocks      = lookup(ingress.value, "cidr_blocks", [])
      ipv6_cidr_blocks = lookup(ingress.value, "ipv6_cidr_blocks", [])
      security_groups  = lookup(ingress.value, "source_security_group_ids", [])
      description      = ingress.value.description
    }
  }

  dynamic "egress" {
    for_each = local.egress_rules_eks

    content {
      from_port   = egress.value.from_port
      to_port     = egress.value.to_port
      protocol    = egress.value.protocol
      cidr_blocks = egress.value.cidr_blocks
      description = egress.value.description
    }
  }

}

####################################
#  Node Group Security Group #
####################################

resource "aws_security_group" "exlerate_eks_cluster_ng_sg" {
  name        = "exl-${var.eks_cluster_name}-ng-sg"
  description = "Security Group defintions for litellm and Langfuse Clusters Nodegroups"
  vpc_id      = var.vpc_id

  dynamic "ingress" {
    for_each = local.ingress_rules_ng

    content {
      from_port        = ingress.value.from_port
      to_port          = ingress.value.to_port
      protocol         = ingress.value.protocol
      self             = lookup(ingress.value, "self", false)
      cidr_blocks      = lookup(ingress.value, "cidr_blocks", [])
      ipv6_cidr_blocks = lookup(ingress.value, "ipv6_cidr_blocks", [])
      security_groups  = lookup(ingress.value, "source_security_group_ids", [])
      description      = ingress.value.description
    }
  }

  dynamic "egress" {
    for_each = local.egress_rules_ng

    content {
      from_port   = egress.value.from_port
      to_port     = egress.value.to_port
      protocol    = egress.value.protocol
      cidr_blocks = egress.value.cidr_blocks
      description = egress.value.description
    }
  }

}

####################################
# RDS DB Security Group #
####################################
resource "aws_security_group" "exlerate_rds_db_sg" {
  name        = "exl-rds-pg-sg-${var.eks_cluster_name}"
  description = "Security Group defintions for RDS cluster"
  vpc_id      = var.vpc_id

  ingress {
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    cidr_blocks = [var.vpc_cidrs]
    description = "Allow CIDR blocks from EKS to connect to RDS"
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

}

####################################
# Redis Cluster Security Group #
####################################
resource "aws_security_group" "exlerate_langfuse_redis_cluster" {
  name        = "exlerate-redis-langfuse-sg-${var.eks_cluster_name}"
  description = "Redis Cache Langfuse Cluster"
  vpc_id      = var.vpc_id

  ingress {
    from_port   = 6379
    to_port     = 6379
    protocol    = "tcp"
    cidr_blocks = [var.vpc_cidrs]
    description = "Allow CIDR blocks from EKS to connect to ElastiCache"
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

}

####################################
# LiteLLM ALB Security Group #
####################################

# LiteLLM ALB Security Group defintions are the same as the NLB
resource "aws_security_group" "exlerate_litellm_alb_sg" {
  name        = "exlerate-litellm-alb-sg-${var.eks_cluster_name}"
  description = "LiteLLM ALB Security Group"
  vpc_id      = var.vpc_id

  dynamic "ingress" {
    for_each = local.alb_ingress_rules_litellm

    content {
      from_port        = ingress.value.from_port
      to_port          = ingress.value.to_port
      protocol         = ingress.value.protocol
      self             = lookup(ingress.value, "self", false)
      cidr_blocks      = lookup(ingress.value, "cidr_blocks", [])
      ipv6_cidr_blocks = lookup(ingress.value, "ipv6_cidr_blocks", [])
      security_groups  = lookup(ingress.value, "source_security_group_ids", [])
      description      = ingress.value.description
    }
  }

  dynamic "egress" {
    for_each = local.egress_rules_eks

    content {
      from_port   = egress.value.from_port
      to_port     = egress.value.to_port
      protocol    = egress.value.protocol
      cidr_blocks = egress.value.cidr_blocks
      description = egress.value.description
    }
  }
}

####################################
# Langfuse ALB Security Group #
####################################

resource "aws_security_group" "exlerate_langfuse_alb_sg" {
  name        = "exlerate-langfuse-alb-sg-${var.eks_cluster_name}"
  description = "Langfuse ALB Security Group"
  vpc_id      = var.vpc_id

  dynamic "ingress" {
    for_each = local.alb_ingress_rules_langfuse

    content {
      from_port        = ingress.value.from_port
      to_port          = ingress.value.to_port
      protocol         = ingress.value.protocol
      self             = lookup(ingress.value, "self", false)
      cidr_blocks      = lookup(ingress.value, "cidr_blocks", [])
      ipv6_cidr_blocks = lookup(ingress.value, "ipv6_cidr_blocks", [])
      security_groups  = lookup(ingress.value, "source_security_group_ids", [])
      description      = ingress.value.description
    }
  }

  dynamic "egress" {
    for_each = local.egress_rules_eks

    content {
      from_port   = egress.value.from_port
      to_port     = egress.value.to_port
      protocol    = egress.value.protocol
      cidr_blocks = egress.value.cidr_blocks
      description = egress.value.description
    }
  }
}

####################################
# Control API ALB Security Group #
####################################

# Control API Security Group defintions
resource "aws_security_group" "exlerate_c1_api_alb_sg" {
  name        = "exlerate-c1-api-alb-sg-${var.eks_cluster_name}"
  description = "Control API ALB Security Group"
  vpc_id      = var.vpc_id

  dynamic "ingress" {
    for_each = local.alb_ingress_rules_c1_api

    content {
      from_port        = ingress.value.from_port
      to_port          = ingress.value.to_port
      protocol         = ingress.value.protocol
      self             = lookup(ingress.value, "self", false)
      cidr_blocks      = lookup(ingress.value, "cidr_blocks", [])
      ipv6_cidr_blocks = lookup(ingress.value, "ipv6_cidr_blocks", [])
      security_groups  = lookup(ingress.value, "source_security_group_ids", [])
      description      = ingress.value.description
    }
  }

  dynamic "egress" {
    for_each = local.egress_rules_eks

    content {
      from_port   = egress.value.from_port
      to_port     = egress.value.to_port
      protocol    = egress.value.protocol
      cidr_blocks = egress.value.cidr_blocks
      description = egress.value.description
    }
  }
}

####################################
# EKS-managed Cluster SG ingress   #
####################################
#
# The EKS-managed cluster SG (cluster_security_group_id) is auto-created by
# EKS and only carries a self-all rule by default. ALB/NLB → pod traffic
# arrives on this SG (pod ENIs inherit it). Without explicit inbound rules the
# ALB health checks and requests time out (Target.Timeout / unhealthy).
#
# Uses aws_vpc_security_group_ingress_rule (one rule per resource) for clean
# per-rule create/destroy — avoids the shared-rule race conditions of the
# legacy aws_security_group_rule resource.
resource "aws_vpc_security_group_ingress_rule" "aigtw_eks_cluster_sg_pod_ports" {
  for_each = local.aigtw_eks_cluster_sg_rules

  security_group_id = aws_eks_cluster.exlerate_eks_cluster.vpc_config[0].cluster_security_group_id
  description       = "TCP ${each.value.port} from ${each.value.cidr} to aigtw EKS pods"
  ip_protocol       = "tcp"
  from_port         = each.value.port
  to_port           = each.value.port
  cidr_ipv4         = each.value.cidr

  tags = {
    Name        = "${var.eks_cluster_name}-eks-cluster-sg-${each.value.port}"
    Environment = var.environment
    ManagedBy   = "terraform"
    Project     = "midas-aigtw"
  }
}
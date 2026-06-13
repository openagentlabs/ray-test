# MIDAS EKS cluster (private API, managed EC2 node group).
# Register in deploy/ecs-app/eks.tf (same pattern as deploy/ecs-app/s3.tf).

locals {
  cluster_name = "${var.cluster_name_prefix}-${var.environment}"
  common_tags = merge(
    {
      Environment = var.environment
      ManagedBy   = "terraform"
      Project     = "midas-eks"
      AccountId   = var.aws_account_id
    },
    var.tags,
  )
}

data "aws_subnet" "cluster" {
  for_each = local.all_subnet_ids
  id       = each.value
}

resource "aws_iam_role" "cluster" {
  name = "${local.cluster_name}-cluster"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "eks.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })

  tags = local.common_tags
}

resource "aws_iam_role_policy_attachment" "cluster_AmazonEKSClusterPolicy" {
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSClusterPolicy"
  role       = aws_iam_role.cluster.name
}

resource "aws_iam_role" "node" {
  name = "${local.cluster_name}-node"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ec2.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })

  tags = local.common_tags
}

resource "aws_iam_role_policy_attachment" "node_AmazonEKSWorkerNodePolicy" {
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSWorkerNodePolicy"
  role       = aws_iam_role.node.name
}

resource "aws_iam_role_policy_attachment" "node_AmazonEKS_CNI_Policy" {
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKS_CNI_Policy"
  role       = aws_iam_role.node.name
}

resource "aws_iam_role_policy_attachment" "node_AmazonEC2ContainerRegistryReadOnly" {
  policy_arn = "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly"
  role       = aws_iam_role.node.name
}

resource "aws_iam_role_policy_attachment" "node_AmazonSSMManagedInstanceCore" {
  count      = var.attach_ssm_policy_to_nodes ? 1 : 0
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
  role       = aws_iam_role.node.name
}

# Allow nodes (Fluent Bit / CloudWatch Agent) to write application logs to
# /midas/<environment>/backend and any other MIDAS CloudWatch log groups.
resource "aws_iam_role_policy" "node_cloudwatch_logs" {
  name = "${local.cluster_name}-node-cloudwatch-logs"
  role = aws_iam_role.node.name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "MidasCloudWatchLogsPut"
        Effect = "Allow"
        Action = [
          "logs:CreateLogStream",
          "logs:PutLogEvents",
          "logs:DescribeLogGroups",
          "logs:DescribeLogStreams",
        ]
        Resource = [
          "arn:aws:logs:${var.aws_region}:*:log-group:/midas/*",
          "arn:aws:logs:${var.aws_region}:*:log-group:/midas/*:*",
        ]
      },
    ]
  })
}

resource "aws_cloudwatch_log_group" "cluster" {
  name              = "/aws/eks/${local.cluster_name}/cluster"
  retention_in_days = var.cluster_log_retention_days

  tags = local.common_tags
}

resource "aws_eks_cluster" "this" {
  # checkov:skip=CKV_AWS_58: Kubernetes-secrets envelope encryption is wired via the dynamic encryption_config block below, controlled by var.secrets_kms_key_arn. Empty string is the dev default (avoids cluster replacement); production must set this in tfvars during a planned maintenance window.
  name     = local.cluster_name
  role_arn = aws_iam_role.cluster.arn
  version  = var.kubernetes_version

  # Explicit bootstrap flag avoids provider drift that can force cluster replacement when only
  # authentication_mode is set (see hashicorp/terraform-provider-aws #38967, #38950).
  access_config {
    authentication_mode                         = "API_AND_CONFIG_MAP"
    bootstrap_cluster_creator_admin_permissions = true
  }

  vpc_config {
    subnet_ids              = var.cluster_subnet_ids
    endpoint_private_access = true
    endpoint_public_access  = false
  }

  # CKV_AWS_58: optional Kubernetes-secrets envelope encryption.
  # Only emitted when var.secrets_kms_key_arn is set, because adding/removing
  # encryption_config on an existing cluster forces replacement.
  dynamic "encryption_config" {
    for_each = var.secrets_kms_key_arn != "" ? [1] : []
    content {
      resources = ["secrets"]
      provider {
        key_arn = var.secrets_kms_key_arn
      }
    }
  }

  enabled_cluster_log_types = var.cluster_enabled_log_types

  depends_on = [
    aws_iam_role_policy_attachment.cluster_AmazonEKSClusterPolicy,
    aws_cloudwatch_log_group.cluster,
  ]

  tags = local.common_tags
}

# HTTPS to the Kubernetes API (private endpoint) from approved corporate / TGW-attached networks
resource "aws_security_group_rule" "cluster_api_https_from_cidrs" {
  count = length(var.cluster_api_https_ingress_cidrs) > 0 ? 1 : 0

  description       = "TCP 443 to EKS cluster security group (Kubernetes API) from approved CIDRs"
  type              = "ingress"
  from_port         = 443
  to_port           = 443
  protocol          = "tcp"
  cidr_blocks       = var.cluster_api_https_ingress_cidrs
  security_group_id = aws_eks_cluster.this.vpc_config[0].cluster_security_group_id
}

# Fortify "Insecure EKS Storage": optional explicit launch template that pins
# node EBS root volumes to a customer-managed KMS key. Created only when
# var.node_ebs_kms_key_arn is set; otherwise the node group uses managed-AMI
# defaults (current dev behaviour, no node-group replacement).
resource "aws_launch_template" "node" {
  count       = var.node_ebs_kms_key_arn != "" ? 1 : 0
  name_prefix = "${local.cluster_name}-node-"

  block_device_mappings {
    device_name = "/dev/xvda"
    ebs {
      volume_size           = var.node_disk_size
      volume_type           = "gp3"
      encrypted             = true
      kms_key_id            = var.node_ebs_kms_key_arn
      delete_on_termination = true
    }
  }

  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 1
  }

  tag_specifications {
    resource_type = "instance"
    tags          = local.common_tags
  }
}

resource "aws_eks_node_group" "this" {
  cluster_name    = aws_eks_cluster.this.name
  node_group_name = "${local.cluster_name}-ng"
  node_role_arn   = aws_iam_role.node.arn
  subnet_ids      = local.node_subnet_ids_effective

  scaling_config {
    desired_size = var.node_desired_size
    max_size     = var.node_max_size
    min_size     = var.node_min_size
  }

  instance_types = var.node_instance_types
  capacity_type  = var.node_capacity_type
  ami_type       = var.node_ami_type
  # disk_size is not valid when launch_template is set; omit when CMK launch template is active.
  disk_size = var.node_ebs_kms_key_arn != "" ? null : var.node_disk_size

  dynamic "launch_template" {
    for_each = var.node_ebs_kms_key_arn != "" ? [1] : []
    content {
      id      = aws_launch_template.node[0].id
      version = "$Latest"
    }
  }

  update_config {
    max_unavailable = 1
  }

  depends_on = [
    aws_iam_role_policy_attachment.node_AmazonEKSWorkerNodePolicy,
    aws_iam_role_policy_attachment.node_AmazonEKS_CNI_Policy,
    aws_iam_role_policy_attachment.node_AmazonEC2ContainerRegistryReadOnly,
  ]

  lifecycle {
    precondition {
      condition = length(distinct([
        for id in var.cluster_subnet_ids : data.aws_subnet.cluster[id].availability_zone
      ])) >= 2
      error_message = "EKS managed node groups require subnets in at least 2 Availability Zones. Add a second subnet from another AZ in the same VPC (see .cursor/config/eks-cluster-config.md)."
    }
    precondition {
      condition = alltrue([
        for id in var.cluster_subnet_ids : data.aws_subnet.cluster[id].vpc_id == var.vpc_id
      ])
      error_message = "Every cluster_subnet_ids entry must belong to vpc_id."
    }
    precondition {
      condition = alltrue([
        for id in local.node_subnet_ids_effective : data.aws_subnet.cluster[id].vpc_id == var.vpc_id
      ])
      error_message = "Every node subnet must belong to vpc_id."
    }
  }

  tags = merge(local.common_tags, { Name = "${local.cluster_name}-ng" })
}

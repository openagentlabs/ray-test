locals {
  _name_prefix_raw = lower(replace("${var.solution.name}-${var.solution.deployment_key}-ray", "_", "-"))
  name_prefix      = can(regex("--", var.solution.deployment_key)) ? local._name_prefix_raw : replace(replace(replace(local._name_prefix_raw, "--", "-"), "--", "-"), "--", "-")

  node_security_group_ids = distinct(concat(
    [var.cluster_security_group_id],
    var.additional_security_group_ids,
  ))

  lustre_client_user_data = <<-EOT
MIME-Version: 1.0
Content-Type: multipart/mixed; boundary="//"

--//
Content-Type: application/node.eks.aws

---
apiVersion: node.eks.aws/v1alpha1
kind: NodeConfig
spec:
  cluster:
    name: ${var.cluster_name}
    apiServerEndpoint: ${var.cluster_endpoint}
    certificateAuthority: ${var.cluster_certificate_authority_data}
    cidr: ${var.cluster_service_ipv4_cidr}

--//
Content-Type: text/x-shellscript; charset="us-ascii"

#!/bin/bash
set -euxo pipefail
dnf install -y lustre-client
echo lustre > /etc/modules-load.d/lustre.conf
modprobe lustre || true

--//--
EOT
}

resource "aws_iam_role" "node" {
  name_prefix = "${substr(local.name_prefix, 0, 32)}-n-"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "ec2.amazonaws.com"
      }
    }]
  })

  tags = {
    purpose   = "eks-node-group"
    cluster   = var.cluster_name
    Component = "ray-compute"
    Service   = "platform"
  }
}

resource "aws_iam_role_policy_attachment" "node_worker" {
  role       = aws_iam_role.node.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSWorkerNodePolicy"
}

resource "aws_iam_role_policy_attachment" "node_cni" {
  role       = aws_iam_role.node.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKS_CNI_Policy"
}

resource "aws_iam_role_policy_attachment" "node_ecr" {
  role       = aws_iam_role.node.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly"
}

resource "aws_iam_role_policy_attachment" "node_ssm" {
  role       = aws_iam_role.node.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_launch_template" "node" {
  name_prefix = "${local.name_prefix}-lt-"

  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 2
  }

  block_device_mappings {
    device_name = "/dev/xvda"

    ebs {
      volume_size           = 100
      volume_type           = "gp3"
      encrypted             = true
      delete_on_termination = true
    }
  }

  monitoring {
    enabled = true
  }

  network_interfaces {
    associate_public_ip_address = false
    delete_on_termination       = true
    device_index                = 0
    security_groups             = local.node_security_group_ids
  }

  tag_specifications {
    resource_type = "instance"
    tags = {
      Name      = "${local.name_prefix}-node"
      purpose   = "eks-ray-node"
      cluster   = var.cluster_name
      Component = "ray-compute"
      Service   = "platform"
    }
  }

  tag_specifications {
    resource_type = "volume"
    tags = {
      Name      = "${local.name_prefix}-node-root"
      purpose   = "eks-ray-node"
      cluster   = var.cluster_name
      Component = "ray-compute"
      Service   = "platform"
    }
  }

  lifecycle {
    create_before_destroy = true
  }

  user_data = var.install_lustre_client ? base64encode(local.lustre_client_user_data) : null
}

resource "aws_eks_node_group" "ray" {
  cluster_name    = var.cluster_name
  node_group_name = "${local.name_prefix}-ng"
  node_role_arn   = aws_iam_role.node.arn
  subnet_ids      = var.subnet_ids
  capacity_type   = "ON_DEMAND"
  instance_types  = [var.node_instance_type]

  scaling_config {
    desired_size = var.node_count
    max_size     = var.node_count
    min_size     = var.node_count
  }

  update_config {
    max_unavailable = 1
  }

  launch_template {
    id      = aws_launch_template.node.id
    version = aws_launch_template.node.latest_version
  }

  labels = {
    (var.node_pool_label_key) = var.node_pool_label_value
  }

  tags = {
    Name      = "${local.name_prefix}-ng"
    purpose   = "eks-ray-node-group"
    cluster   = var.cluster_name
    Component = "ray-compute"
    Service   = "platform"
  }

  depends_on = [
    aws_iam_role_policy_attachment.node_worker,
    aws_iam_role_policy_attachment.node_cni,
    aws_iam_role_policy_attachment.node_ecr,
    aws_iam_role_policy_attachment.node_ssm,
  ]
}

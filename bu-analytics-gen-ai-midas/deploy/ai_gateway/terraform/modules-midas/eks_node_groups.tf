resource "aws_eks_node_group" "eks_nodegroup" {
  cluster_name    = aws_eks_cluster.exlerate_eks_cluster.name
  node_group_name = "${var.eks_cluster_name}-ndp"
  node_role_arn   = aws_iam_role.eks_node_group_role.arn
  subnet_ids      = local.eks_subnet_ids
  instance_types  = var.instance_type
  ami_type        = var.ami_type

  launch_template {
    id      = aws_launch_template.init_nodegroup.id
    version = "$Latest"
  }

  scaling_config {
    desired_size = var.scaling_config.desired_size
    max_size     = var.scaling_config.max_size
    min_size     = var.scaling_config.min_size
  }

  update_config {
    max_unavailable = 1
    update_strategy = "DEFAULT"
  }

  depends_on = [aws_kms_key.eks_ec2_ng_kms,
    aws_iam_role.eks_node_group_role,
  aws_launch_template.init_nodegroup]

  lifecycle {
    ignore_changes = [launch_template[0].version, subnet_ids]
  }

}

resource "aws_iam_instance_profile" "eks_nodegroup" {
  name = "${var.eks_cluster_name}-np"
  role = aws_iam_role.eks_node_group_role.name
}

resource "aws_launch_template" "init_nodegroup" {
  name                   = "exl-${var.eks_cluster_name}-ng-launch-template"
  update_default_version = true
  #name_prefix = "exlerate-${var.environment}-def-ng"
  network_interfaces {
    security_groups = [
      aws_security_group.exlerate_eks_cluster_sg.id,
      aws_eks_cluster.exlerate_eks_cluster.vpc_config[0].cluster_security_group_id
    ]
  }

  metadata_options {
    http_endpoint               = "enabled"  # must be enabled
    http_tokens                 = "required" # enforces IMDSv2 (recommended)
    http_put_response_hop_limit = 1          # CKV_AWS_341: IRSA is enabled, so pods do not need IMDS hops (was 2)
  }

  block_device_mappings {
    device_name = "/dev/xvda"
    ebs {
      volume_type = "gp3"
      volume_size = 30
      throughput  = "125"
      iops        = "3000"
      encrypted   = true
      kms_key_id  = aws_kms_key.eks_ec2_ng_kms.arn
    }
  }

  depends_on = [aws_kms_key.eks_ec2_ng_kms]

}

# Clickhouse nodegroup definition to run OLAP DB
resource "aws_eks_node_group" "clickhouse_eks_nodegroup" {
  cluster_name    = aws_eks_cluster.exlerate_eks_cluster.name
  node_group_name = "${var.eks_cluster_name}-clickhouse-ndp"
  node_role_arn   = aws_iam_role.eks_node_group_role.arn
  subnet_ids      = local.eks_subnet_ids
  instance_types  = var.clickhouse_instance_type
  ami_type        = var.ami_type

  launch_template {
    id      = aws_launch_template.ch_nodegroup.id
    version = "$Latest"
  }

  scaling_config {
    desired_size = var.ch_scaling_config.desired_size
    max_size     = var.ch_scaling_config.max_size
    min_size     = var.ch_scaling_config.min_size
  }

  update_config {
    max_unavailable = 1
    update_strategy = "DEFAULT"
  }

  depends_on = [aws_kms_key.eks_ec2_ng_kms,
    aws_iam_role.eks_node_group_role,
  aws_launch_template.init_nodegroup]

  lifecycle {
    ignore_changes = [launch_template[0].version, subnet_ids]
  }
  labels = {
    Workload = "clickhouse"
  }
}

resource "aws_iam_instance_profile" "clickhouse_eks_nodegroup_ip" {
  name = "${var.eks_cluster_name}-np-clickhouse"
  role = aws_iam_role.eks_node_group_role.name
}

resource "aws_launch_template" "ch_nodegroup" {
  name                   = "exl-${var.eks_cluster_name}-chng-launch-template"
  update_default_version = true
  #name_prefix = "exlerate-ch-${var.environment}-ng"

  network_interfaces {
    security_groups = [
      aws_security_group.exlerate_eks_cluster_sg.id,
      aws_eks_cluster.exlerate_eks_cluster.vpc_config[0].cluster_security_group_id
    ]
  }

  metadata_options {
    http_endpoint               = "enabled"  # must be enabled
    http_tokens                 = "required" # enforces IMDSv2 (recommended)
    http_put_response_hop_limit = 1          # CKV_AWS_341: IRSA is enabled, so pods do not need IMDS hops (was 2)
  }

  block_device_mappings {
    device_name = "/dev/xvda"
    ebs {
      volume_type = "gp3"
      volume_size = 100
      throughput  = "125"
      iops        = "3000"
      encrypted   = true
      kms_key_id  = aws_kms_key.eks_ec2_ng_kms.arn
    }
  }
  # Do not remove this user_data block, it is required for the 
  # EKS node group to inject additional metadata to the node.
  user_data = base64encode(<<-EOF
Content-Type: multipart/mixed; boundary="==MYBOUNDARY=="
MIME-Version: 1.0

--==MYBOUNDARY==
Content-Type: text/x-shellscript; charset="us-ascii"

#!/bin/bash
/etc/eks/bootstrap.sh ${aws_eks_cluster.exlerate_eks_cluster.name} \
  --kubelet-extra-args '--node-labels=Workload=clickhouse'

--==MYBOUNDARY==--
EOF
  )

  depends_on = [aws_kms_key.eks_ec2_ng_kms]

}
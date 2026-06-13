resource "aws_iam_role" "cluster" {
  name_prefix = "${substr(var.cluster_name, 0, 24)}-eks-c-"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "eks.amazonaws.com"
      }
    }]
  })

  tags = {
    purpose = "eks-cluster"
  }
}

resource "aws_iam_role_policy_attachment" "cluster_policy" {
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSClusterPolicy"
  role       = aws_iam_role.cluster.name
}

resource "aws_iam_role" "fargate_pod_execution" {
  name = "${var.cluster_name}-eks-fargate-exec"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "eks-fargate-pods.amazonaws.com"
      }
    }]
  })

  tags = {
    purpose = "eks-fargate-pod-execution"
  }
}

resource "aws_iam_role_policy_attachment" "fargate_pod_execution" {
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSFargatePodExecutionRolePolicy"
  role       = aws_iam_role.fargate_pod_execution.name
}

resource "aws_cloudwatch_log_group" "control_plane" {
  name              = "/aws/eks/${var.cluster_name}/cluster"
  retention_in_days = var.log_retention_in_days

  tags = {
    purpose  = "eks-control-plane"
    cluster  = var.cluster_name
    solution = var.solution.name
  }
}

resource "aws_eks_cluster" "this" {
  name     = var.cluster_name
  role_arn = aws_iam_role.cluster.arn
  version  = var.kubernetes_version

  enabled_cluster_log_types = var.control_plane_log_types

  vpc_config {
    subnet_ids             = var.subnet_ids
    endpoint_public_access = true
    security_group_ids     = var.cluster_security_group_ids
  }

  depends_on = [
    aws_iam_role_policy_attachment.cluster_policy,
    aws_cloudwatch_log_group.control_plane,
  ]

  tags = {
    purpose = "eks-fargate"
  }
}

data "tls_certificate" "cluster" {
  url = aws_eks_cluster.this.identity[0].oidc[0].issuer
}

resource "aws_iam_openid_connect_provider" "cluster" {
  client_id_list  = ["sts.amazonaws.com"]
  thumbprint_list = [data.tls_certificate.cluster.certificates[0].sha1_fingerprint]
  url             = aws_eks_cluster.this.identity[0].oidc[0].issuer

  tags = {
    purpose = "eks-irsa"
  }
}

resource "aws_eks_fargate_profile" "kube_system" {
  cluster_name           = aws_eks_cluster.this.name
  fargate_profile_name   = "kube-system"
  pod_execution_role_arn = aws_iam_role.fargate_pod_execution.arn
  subnet_ids             = var.fargate_subnet_ids

  selector {
    namespace = "kube-system"
  }

  tags = {
    purpose = "eks-fargate-kube-system"
  }
}

resource "aws_eks_fargate_profile" "workloads" {
  count = var.fargate_workloads_namespace_enabled ? 1 : 0

  cluster_name           = aws_eks_cluster.this.name
  fargate_profile_name   = var.namespace
  pod_execution_role_arn = aws_iam_role.fargate_pod_execution.arn
  subnet_ids             = var.fargate_subnet_ids

  selector {
    namespace = var.namespace
  }

  tags = {
    purpose = "eks-fargate-workloads"
  }
}

resource "aws_eks_addon" "vpc_cni" {
  cluster_name = aws_eks_cluster.this.name
  addon_name   = "vpc-cni"
}

resource "aws_eks_addon" "coredns" {
  cluster_name = aws_eks_cluster.this.name
  addon_name   = "coredns"

  configuration_values = jsonencode({
    computeType = "Fargate"
  })

  resolve_conflicts_on_create = "OVERWRITE"
  resolve_conflicts_on_update = "OVERWRITE"

  depends_on = [
    aws_eks_fargate_profile.kube_system,
    aws_eks_fargate_profile.workloads,
  ]

  timeouts {
    create = "40m"
    update = "40m"
  }
}

resource "aws_eks_addon" "kube_proxy" {
  cluster_name = aws_eks_cluster.this.name
  addon_name   = "kube-proxy"
}

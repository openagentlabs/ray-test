resource "aws_eks_cluster" "exlerate_eks_cluster" {
  #checkov:skip=CKV_AWS_339:Kubernetes 1.35 is a supported EKS version per AWS docs; Checkov 3.2.529 passes this check -- ISG scanner lag in its allowed-version list causes false positive
  name     = var.eks_cluster_name
  role_arn = aws_iam_role.eks_cluster_role.arn

  access_config {
    authentication_mode = "API_AND_CONFIG_MAP"
  }

  version = var.eks_cluster_version

  vpc_config {
    subnet_ids         = local.eks_subnet_ids
    security_group_ids = [aws_security_group.exlerate_eks_cluster_sg.id]
    # Fortify "Improper EKS Network Access Control" / architecture.mdc:
    # private-by-default — the API endpoint is reachable only from within
    # vpc-0c4d673f3e95a93eb (Jenkins agents, jumpbox via SSM port-forward,
    # peered networks via tgw-0ec391fa73943d562).
    endpoint_private_access = true
    endpoint_public_access  = false
  }

  enabled_cluster_log_types = var.eks_log_types

  encryption_config {
    provider {
      key_arn = aws_kms_key.eks_cluster_kms_key.arn
    }
    resources = ["secrets"]
  }

  # Required to ensure cluster can delete EC2 infra before being deleted itself
  depends_on = [
    aws_iam_role.eks_cluster_role,
    aws_cloudwatch_log_group.exelerate_cw_group
  ]

  lifecycle {
    ignore_changes = [vpc_config.0.subnet_ids]
  }
}

##################################################
#     Create Namespaces
##################################################
resource "kubernetes_namespace_v1" "c1_api" {
  metadata {
    name = var.c1_api_ns

    labels = {
      "app.kubernetes.io/managed-by" = "Helm"
    }

    annotations = {
      "meta.helm.sh/release-name"      = "c1-api"
      "meta.helm.sh/release-namespace" = var.c1_api_ns
    }
  }

  depends_on = [aws_eks_cluster.exlerate_eks_cluster]
}

resource "kubernetes_namespace_v1" "clickhouse" {
  metadata {
    name = var.ch_ns

    labels = {
      "app.kubernetes.io/managed-by" = "Helm"
    }

    annotations = {
      "meta.helm.sh/release-name"      = "clickhouse"
      "meta.helm.sh/release-namespace" = var.ch_ns
    }
  }

  depends_on = [aws_eks_cluster.exlerate_eks_cluster]
}

resource "kubernetes_namespace_v1" "litellm" {
  metadata {
    name = var.litellm_ns
  }

  depends_on = [aws_eks_cluster.exlerate_eks_cluster]
}

resource "kubernetes_namespace_v1" "langfuse" {
  metadata {
    name = var.langfuse_ns

    labels = {
      "app.kubernetes.io/managed-by" = "Helm"
    }

    annotations = {
      "meta.helm.sh/release-name"      = "langfuse"
      "meta.helm.sh/release-namespace" = var.langfuse_ns
    }
  }

  lifecycle {
    ignore_changes = [
      metadata[0].labels
    ]
  }

  depends_on = [aws_eks_cluster.exlerate_eks_cluster]
}

resource "aws_iam_openid_connect_provider" "exlerate_eks_cluster" {
  url = one(one(aws_eks_cluster.exlerate_eks_cluster.identity).oidc).issuer

  client_id_list = [
    "sts.amazonaws.com",
  ]
}

data "aws_eks_addon_version" "add_on_version_control" {
  for_each           = toset(keys(var.eks_addons))
  addon_name         = each.value
  kubernetes_version = aws_eks_cluster.exlerate_eks_cluster.version
  most_recent        = true
}

resource "aws_eks_addon" "eks_addons" {
  for_each = var.eks_addons

  cluster_name  = aws_eks_cluster.exlerate_eks_cluster.name
  addon_name    = each.key
  addon_version = data.aws_eks_addon_version.add_on_version_control[each.key].version

  depends_on = [
    aws_eks_node_group.eks_nodegroup
  ]
}

output "cluster_name" {
  value = aws_eks_cluster.exlerate_eks_cluster.name
}

output "cluster_endpoint" {
  value = aws_eks_cluster.exlerate_eks_cluster.endpoint
}

output "cluster_ca" {
  value     = aws_eks_cluster.exlerate_eks_cluster.certificate_authority[0].data
  sensitive = true
}

output "oidc_url" {
  value = replace(one(one(aws_eks_cluster.exlerate_eks_cluster.identity).oidc).issuer, "https://", "")
}

##################################################
#     EKS API Permission Definitions
##################################################
resource "aws_eks_access_entry" "EKS_Jenkins_Admin_definition" {
  cluster_name  = aws_eks_cluster.exlerate_eks_cluster.name
  principal_arn = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/EXLJenkinsCrossAccountRole-BU"
  type          = "STANDARD"
}

resource "aws_eks_access_policy_association" "jenkins_cluster_admin" {
  cluster_name  = aws_eks_cluster.exlerate_eks_cluster.name
  principal_arn = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/EXLJenkinsCrossAccountRole-BU"
  policy_arn    = "arn:aws:eks::aws:cluster-access-policy/AmazonEKSClusterAdminPolicy"

  access_scope {
    type = "cluster"
  }
}

resource "aws_eks_access_entry" "EKS_Admin_definition" {
  count         = var.environment == "uat" ? 0 : 1 # Roles not permitted for higher environments
  cluster_name  = aws_eks_cluster.exlerate_eks_cluster.name
  principal_arn = var.architect_role_arn
  type          = "STANDARD"
}

resource "aws_eks_access_policy_association" "cluster_admin" {
  count         = var.environment == "uat" ? 0 : 1 # Roles not permitted for higher environments
  cluster_name  = aws_eks_cluster.exlerate_eks_cluster.name
  principal_arn = var.architect_role_arn
  policy_arn    = "arn:aws:eks::aws:cluster-access-policy/AmazonEKSClusterAdminPolicy"

  access_scope {
    type = "cluster"
  }
}

resource "aws_eks_access_entry" "EKS_developer_definition" {
  count         = var.environment == "uat" ? 0 : 1 # Roles not permitted for higher environments
  cluster_name  = aws_eks_cluster.exlerate_eks_cluster.name
  principal_arn = var.developer_role_arn
  type          = "STANDARD"
}

resource "aws_eks_access_policy_association" "cluster_developer" {
  count         = var.environment == "uat" ? 0 : 1 # Roles not permitted for higher environments
  cluster_name  = aws_eks_cluster.exlerate_eks_cluster.name
  principal_arn = var.developer_role_arn
  policy_arn    = "arn:aws:eks::aws:cluster-access-policy/AmazonEKSEditPolicy"

  access_scope {
    type = "cluster"
  }
}

resource "aws_eks_access_entry" "EKS_ro_definition" {
  cluster_name  = aws_eks_cluster.exlerate_eks_cluster.name
  principal_arn = var.admin_ro_arn
  type          = "STANDARD"
}

resource "aws_eks_access_policy_association" "cluster_ro" {
  cluster_name  = aws_eks_cluster.exlerate_eks_cluster.name
  principal_arn = var.admin_ro_arn
  policy_arn    = "arn:aws:eks::aws:cluster-access-policy/AmazonEKSViewPolicy"

  access_scope {
    type = "cluster"
  }
}
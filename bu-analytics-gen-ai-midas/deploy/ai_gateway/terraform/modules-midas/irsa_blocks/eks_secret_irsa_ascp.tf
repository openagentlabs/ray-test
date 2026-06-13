# IRSA Role for EKS Cluster to talk with resources in AWS
resource "aws_iam_role" "eks_irsa_handler" {
  name                  = "exl-${var.eks_cluster_name}-shr-${var.application}"
  path                  = "/"
  max_session_duration  = 3600
  description           = "This IAM Role defines a trust relationship between OIDC EKS endpoint and AWS resources"
  force_detach_policies = true
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Federated = "arn:aws:iam::${var.account_id}:oidc-provider/${var.eks_oidc_url}"
        }
        Action = "sts:AssumeRoleWithWebIdentity",
        Condition = {
          StringEquals = {
            "${var.eks_oidc_url}:sub" : "system:serviceaccount:${var.eks_namespace}:${var.irsa_account_name}", # Can be filtered to namespace and app
            "${var.eks_oidc_url}:aud" : "sts.amazonaws.com"
          }
        }
      }
    ]
  })
}

# Attach AWS SSM Parameter and AWS Secrets Manager policies
resource "aws_iam_role_policy_attachment" "secrets_role_handler_policy" {
  count      = length(var.policy_arns)
  role       = aws_iam_role.eks_irsa_handler.name
  policy_arn = var.policy_arns[count.index]
}

# Linkage between EKS ServiceAccount and predefined IAM role
resource "kubernetes_service_account_v1" "irsa_sa" {
  metadata {
    name      = var.irsa_account_name
    namespace = var.eks_namespace

    annotations = {
      "eks.amazonaws.com/role-arn" = aws_iam_role.eks_irsa_handler.arn
    }
  }

  dynamic "image_pull_secret" {
    for_each = var.image_pull_secrets
    content {
      name = image_pull_secret.value
    }
  }
}
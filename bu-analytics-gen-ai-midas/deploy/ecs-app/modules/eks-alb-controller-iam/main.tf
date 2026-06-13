# IRSA + IAM policy for AWS Load Balancer Controller (internal ALBs via Ingress).
# Policy JSON: upstream kubernetes-sigs/aws-load-balancer-controller (v2.8.1).

data "tls_certificate" "eks_oidc" {
  url = var.oidc_issuer_url
}

locals {
  common_tags = merge(
    {
      Environment = var.environment
      ManagedBy   = "terraform"
      Project     = "midas-eks"
      AccountId   = var.aws_account_id
    },
    var.tags,
  )

  # Issuer host/path without scheme - used in IAM condition keys for IRSA.
  oidc_issuer_host_path = replace(var.oidc_issuer_url, "https://", "")

  # IAM OIDC thumbprint must match the root CA; use last cert in the chain when present.
  oidc_thumbprint = data.tls_certificate.eks_oidc.certificates[length(data.tls_certificate.eks_oidc.certificates) - 1].sha1_fingerprint
}

resource "aws_iam_openid_connect_provider" "eks" {
  client_id_list  = ["sts.amazonaws.com"]
  thumbprint_list = [local.oidc_thumbprint]
  url             = var.oidc_issuer_url

  tags = local.common_tags
}

resource "aws_iam_policy" "aws_load_balancer_controller" {
  name        = "${var.cluster_name}-AWSLoadBalancerControllerIAMPolicy"
  description = "AWS Load Balancer Controller (kubernetes-sigs); scoped to ${var.cluster_name}"
  policy      = file("${path.module}/files/iam_policy.json")

  tags = local.common_tags
}

resource "aws_iam_role" "aws_load_balancer_controller" {
  name = "${var.cluster_name}-aws-load-balancer-controller"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Federated = aws_iam_openid_connect_provider.eks.arn
      }
      Action = "sts:AssumeRoleWithWebIdentity"
      Condition = {
        StringEquals = {
          "${local.oidc_issuer_host_path}:aud" = "sts.amazonaws.com"
          "${local.oidc_issuer_host_path}:sub" = "system:serviceaccount:${var.kubernetes_namespace}:${var.service_account_name}"
        }
      }
    }]
  })

  tags = local.common_tags
}

resource "aws_iam_role_policy_attachment" "aws_load_balancer_controller" {
  role       = aws_iam_role.aws_load_balancer_controller.name
  policy_arn = aws_iam_policy.aws_load_balancer_controller.arn
}

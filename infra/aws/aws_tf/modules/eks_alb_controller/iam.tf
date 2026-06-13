data "aws_iam_policy_document" "alb_controller_assume" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRoleWithWebIdentity"]
    principals {
      type        = "Federated"
      identifiers = [var.oidc_provider_arn]
    }
    condition {
      test     = "StringEquals"
      variable = "${var.oidc_provider_url}:sub"
      values   = ["system:serviceaccount:kube-system:${local.service_account_name}"]
    }
    condition {
      test     = "StringEquals"
      variable = "${var.oidc_provider_url}:aud"
      values   = ["sts.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "alb_controller" {
  name_prefix        = "${substr("${lower(replace(var.solution.name, "_", "-"))}-${var.solution.deployment_key}", 0, 26)}-alb-"
  assume_role_policy = data.aws_iam_policy_document.alb_controller_assume.json

  tags = {
    purpose   = "eks-alb-controller-irsa"
    cluster   = var.cluster_name
    Component = "load-balancing"
    Service   = "platform"
  }
}

resource "aws_iam_policy" "alb_controller" {
  name_prefix = "${substr("${lower(replace(var.solution.name, "_", "-"))}-${var.solution.deployment_key}", 0, 26)}-alb-"
  description = "AWS Load Balancer Controller permissions for EKS cluster ${var.cluster_name}"
  policy      = file("${path.module}/iam_policy.json")

  tags = {
    purpose = "eks-alb-controller"
    cluster = var.cluster_name
  }
}

resource "aws_iam_role_policy_attachment" "alb_controller" {
  role       = aws_iam_role.alb_controller.name
  policy_arn = aws_iam_policy.alb_controller.arn
}

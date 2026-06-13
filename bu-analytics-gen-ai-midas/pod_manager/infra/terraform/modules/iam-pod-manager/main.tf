# IRSA trust: derive OIDC host from provider ARN (arn:aws:iam::ACCOUNT:oidc-provider/HOST)
locals {
  oidc_host = replace(var.oidc_provider_arn, "/^arn:aws:iam::[0-9]+:oidc-provider\\//", "")
}

data "aws_iam_policy_document" "assume_role" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [var.oidc_provider_arn]
    }

    condition {
      test     = "StringEquals"
      variable = "${local.oidc_host}:aud"
      values   = ["sts.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "${local.oidc_host}:sub"
      values = [
        "system:serviceaccount:${var.namespace}:${var.service_account_name}",
      ]
    }
  }
}

resource "aws_iam_role" "pod_manager" {
  name               = var.role_name
  assume_role_policy = data.aws_iam_policy_document.assume_role.json
  tags               = var.tags
}

# The routing tier reads the shared Postgres connection string (DATABASE_URL)
# from Secrets Manager. Only granted when a secret ARN is supplied.
data "aws_iam_policy_document" "database_secret" {
  count = var.database_url_secret_arn == "" ? 0 : 1

  statement {
    sid       = "ReadDatabaseSecret"
    effect    = "Allow"
    actions   = ["secretsmanager:GetSecretValue"]
    resources = [var.database_url_secret_arn]
  }
}

resource "aws_iam_role_policy" "database_secret" {
  count  = var.database_url_secret_arn == "" ? 0 : 1
  name   = "${var.role_name}-database-secret"
  role   = aws_iam_role.pod_manager.id
  policy = data.aws_iam_policy_document.database_secret[0].json
}

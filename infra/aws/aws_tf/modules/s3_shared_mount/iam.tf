data "aws_iam_policy_document" "s3_csi_assume" {
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

resource "aws_iam_role" "s3_csi" {
  name_prefix        = "${substr(local.name_prefix, 0, 26)}-"
  assume_role_policy = data.aws_iam_policy_document.s3_csi_assume.json

  tags = {
    purpose   = "eks-s3-csi-irsa"
    cluster   = var.cluster_name
    Component = "shared-s3-files"
    Service   = "platform"
  }
}

data "aws_iam_policy_document" "s3_csi" {
  statement {
    sid    = "S3SharedFilesList"
    effect = "Allow"
    actions = [
      "s3:ListBucket",
      "s3:GetBucketLocation",
    ]
    resources = [var.bucket_arn]

    condition {
      test     = "StringLike"
      variable = "s3:prefix"
      values   = local.list_bucket_prefixes
    }
  }

  statement {
    sid    = "S3SharedFilesObjects"
    effect = "Allow"
    actions = [
      "s3:GetObject",
      "s3:PutObject",
      "s3:DeleteObject",
      "s3:AbortMultipartUpload",
      "s3:ListMultipartUploadParts",
    ]
    resources = [local.s3_object_resource_arn]
  }
}

resource "aws_iam_policy" "s3_csi" {
  name_prefix = "${substr(local.name_prefix, 0, 26)}-"
  description = "Mountpoint S3 CSI driver permissions for ${var.bucket_name} (${local.normalized_bucket_key_prefix})"
  policy      = data.aws_iam_policy_document.s3_csi.json

  tags = {
    purpose = "eks-s3-csi"
    cluster = var.cluster_name
  }
}

resource "aws_iam_role_policy_attachment" "s3_csi" {
  role       = aws_iam_role.s3_csi.name
  policy_arn = aws_iam_policy.s3_csi.arn
}

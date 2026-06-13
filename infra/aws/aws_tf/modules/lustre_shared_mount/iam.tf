data "aws_iam_policy_document" "fsx_csi_assume" {
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

resource "aws_iam_role" "fsx_csi" {
  name_prefix        = "${substr(local.name_prefix, 0, 26)}-"
  assume_role_policy = data.aws_iam_policy_document.fsx_csi_assume.json

  tags = {
    purpose   = "eks-fsx-csi-irsa"
    cluster   = var.cluster_name
    Component = "shared-lustre"
    Service   = "platform"
  }
}

data "aws_iam_policy_document" "fsx_csi" {
  statement {
    sid    = "FsxDescribe"
    effect = "Allow"
    actions = [
      "fsx:DescribeFileSystems",
      "fsx:DescribeDataRepositoryTasks",
      "fsx:DescribeStorageVirtualMachines",
      "fsx:DescribeVolumes",
    ]
    resources = ["*"]
  }
}

resource "aws_iam_policy" "fsx_csi" {
  name_prefix = "${substr(local.name_prefix, 0, 26)}-"
  description = "AWS FSx CSI driver permissions for static Lustre mounts on ${var.cluster_name}"
  policy      = data.aws_iam_policy_document.fsx_csi.json

  tags = {
    purpose = "eks-fsx-csi"
    cluster = var.cluster_name
  }
}

resource "aws_iam_role_policy_attachment" "fsx_csi" {
  role       = aws_iam_role.fsx_csi.name
  policy_arn = aws_iam_policy.fsx_csi.arn
}

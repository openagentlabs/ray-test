module "ecr" {
  for_each = local.enabled_workloads
  source   = "../ecr_repository"

  solution        = var.solution
  workload_key    = each.key
  repository_name = "${local.ecr_prefix}-${each.value.ecr_suffix}"
}

data "aws_iam_policy_document" "shared_irsa_assume" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRoleWithWebIdentity"]
    principals {
      type        = "Federated"
      identifiers = [var.oidc_provider_arn]
    }
    condition {
      test     = "StringEquals"
      variable = "${var.oidc_provider_url}:aud"
      values   = ["sts.amazonaws.com"]
    }
    condition {
      test     = "StringEquals"
      variable = "${var.oidc_provider_url}:sub"
      values = [
        for sa in local.irsa_service_account_names :
        "system:serviceaccount:${var.namespace}:${sa}"
      ]
    }
  }
}

resource "aws_iam_role" "shared_workload" {
  name_prefix        = "${var.solution.name}-eks-workload-"
  assume_role_policy = data.aws_iam_policy_document.shared_irsa_assume.json

  tags = {
    purpose = "eks-irsa-shared-data-plane"
  }
}

resource "aws_iam_role_policy_attachment" "shared_workload_logs" {
  role       = aws_iam_role.shared_workload.name
  policy_arn = var.application_logs_put_policy_arn
}

data "aws_iam_policy_document" "shared_aws_data_plane" {
  dynamic "statement" {
    for_each = length(var.dynamodb_table_arns) > 0 ? [1] : []
    content {
      sid    = "DynamoDbListTables"
      effect = "Allow"
      actions = [
        "dynamodb:ListTables",
      ]
      resources = ["*"]
    }
  }

  dynamic "statement" {
    for_each = length(var.dynamodb_table_arns) > 0 ? [1] : []
    content {
      sid    = "DynamoDbDataPlane"
      effect = "Allow"
      actions = [
        "dynamodb:BatchGetItem",
        "dynamodb:BatchWriteItem",
        "dynamodb:DeleteItem",
        "dynamodb:GetItem",
        "dynamodb:PutItem",
        "dynamodb:Query",
        "dynamodb:Scan",
        "dynamodb:UpdateItem",
        "dynamodb:DescribeTable",
      ]
      resources = concat(var.dynamodb_table_arns, [for arn in var.dynamodb_table_arns : "${arn}/index/*"])
    }
  }

  dynamic "statement" {
    for_each = length(var.s3_bucket_arns) > 0 ? [1] : []
    content {
      sid       = "S3GeneralBuckets"
      effect    = "Allow"
      actions   = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject", "s3:ListBucket"]
      resources = flatten([for arn in var.s3_bucket_arns : [arn, "${arn}/*"]])
    }
  }

  dynamic "statement" {
    for_each = var.sns_topic_arn != "" ? [1] : []
    content {
      sid       = "SnsPublish"
      effect    = "Allow"
      actions   = ["sns:Publish", "sns:GetTopicAttributes"]
      resources = [var.sns_topic_arn]
    }
  }
}

resource "aws_iam_role_policy" "shared_aws_data_plane" {
  count = length(var.dynamodb_table_arns) > 0 || length(var.s3_bucket_arns) > 0 || var.sns_topic_arn != "" ? 1 : 0

  name_prefix = "${var.solution.name}-eks-data-"
  role        = aws_iam_role.shared_workload.id
  policy      = data.aws_iam_policy_document.shared_aws_data_plane.json
}

resource "aws_iam_role_policy_attachment" "bedrock_task_logs" {
  role       = var.bedrock_task_role_name
  policy_arn = var.application_logs_put_policy_arn
}

resource "aws_iam_role_policy_attachment" "arch_diagram_agent_bedrock_task_logs" {
  role       = var.arch_diagram_agent_bedrock_task_role_name
  policy_arn = var.application_logs_put_policy_arn
}

resource "aws_iam_role_policy_attachment" "document_storage_task_logs" {
  role       = var.document_storage_task_role_name
  policy_arn = var.application_logs_put_policy_arn
}

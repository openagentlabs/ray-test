###############################################################################
# Trust: EKS IRSA (when irsa_trust is set) or same-account root for local dev.
###############################################################################

data "aws_iam_policy_document" "assume_document_storage" {
  dynamic "statement" {
    for_each = var.irsa_trust != null ? [var.irsa_trust] : []
    content {
      sid     = "AssumeFromEksIrsa"
      effect  = "Allow"
      actions = ["sts:AssumeRoleWithWebIdentity"]
      principals {
        type        = "Federated"
        identifiers = [statement.value.oidc_provider_arn]
      }
      condition {
        test     = "StringEquals"
        variable = "${statement.value.oidc_provider_url}:sub"
        values   = ["system:serviceaccount:${statement.value.namespace}:${statement.value.service_account}"]
      }
      condition {
        test     = "StringEquals"
        variable = "${statement.value.oidc_provider_url}:aud"
        values   = ["sts.amazonaws.com"]
      }
    }
  }

  dynamic "statement" {
    for_each = var.irsa_trust == null ? [1] : []
    content {
      sid    = "AssumeFromAccount"
      effect = "Allow"

      actions = ["sts:AssumeRole"]

      principals {
        type        = "AWS"
        identifiers = ["arn:aws:iam::${var.solution.account_id}:root"]
      }
    }
  }
}

module "role" {
  source = "../iam_role"

  solution                = var.solution
  role_name               = var.role_name
  assume_role_policy_json = data.aws_iam_policy_document.assume_document_storage.json
  description             = "DynamoDB, S3, and Bedrock embeddings for document-storage.svc."
  managed_policy_arns     = []
  additional_tags = {
    "iam:Service" = "document-storage"
  }
}

locals {
  registry_and_groups_arns = [
    var.docstore_registry_table_arn,
    var.docstore_groups_table_arn,
  ]
  registry_and_groups_index_arns = [
    for arn in local.registry_and_groups_arns : "${arn}/index/*"
  ]
}

data "aws_iam_policy_document" "document_storage_data_plane" {
  statement {
    sid    = "DynamoDbListTablesForHealthCheck"
    effect = "Allow"
    actions = [
      "dynamodb:ListTables",
    ]
    resources = ["*"]
  }

  statement {
    sid    = "DynamoDbRegistryAndGroups"
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
    resources = concat(local.registry_and_groups_arns, local.registry_and_groups_index_arns)
  }

  statement {
    sid    = "DynamoDbGroupPhysicalTables"
    effect = "Allow"
    actions = [
      "dynamodb:BatchGetItem",
      "dynamodb:BatchWriteItem",
      "dynamodb:CreateTable",
      "dynamodb:DeleteItem",
      "dynamodb:DeleteTable",
      "dynamodb:DescribeTable",
      "dynamodb:GetItem",
      "dynamodb:PutItem",
      "dynamodb:Query",
      "dynamodb:Scan",
      "dynamodb:UpdateItem",
    ]
    resources = [
      var.group_physical_table_arn_wildcard,
      "${var.group_physical_table_arn_wildcard}/index/*",
    ]
  }

  statement {
    sid    = "S3DocstoreAttachments"
    effect = "Allow"
    actions = [
      "s3:GetObject",
      "s3:PutObject",
      "s3:DeleteObject",
      "s3:ListBucket",
    ]
    resources = [
      var.attachments_bucket_arn,
      "${var.attachments_bucket_arn}/*",
    ]
  }

  statement {
    sid    = "BedrockTitanEmbeddings"
    effect = "Allow"
    actions = [
      "bedrock:InvokeModel",
    ]
    resources = var.bedrock_embed_resource_arns
  }
}

resource "aws_iam_role_policy" "document_storage_data_plane" {
  name   = "${var.role_name}-data-plane"
  role   = module.role.role_name
  policy = data.aws_iam_policy_document.document_storage_data_plane.json
}

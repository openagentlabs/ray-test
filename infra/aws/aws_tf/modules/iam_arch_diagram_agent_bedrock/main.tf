###############################################################################
# Trust: EKS IRSA (when irsa_trust is set) or same-account root for local dev.
###############################################################################

data "aws_iam_policy_document" "assume_arch_diagram_agent" {
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
  assume_role_policy_json = data.aws_iam_policy_document.assume_arch_diagram_agent.json
  description             = "Bedrock Runtime invoke for arch.diagram.agent.svc (Claude Sonnet family)."
  managed_policy_arns     = []
  additional_tags = {
    "iam:Service" = "arch-diagram-agent"
  }
}

data "aws_iam_policy_document" "bedrock_invoke" {
  statement {
    sid    = "BedrockConverseAndInvoke"
    effect = "Allow"

    actions = [
      "bedrock:InvokeModel",
      "bedrock:InvokeModelWithResponseStream",
      "bedrock:Converse",
      "bedrock:ConverseStream",
      "bedrock:CountTokens",
    ]

    resources = var.bedrock_invoke_resource_arns
  }
}

resource "aws_iam_role_policy" "bedrock_invoke" {
  name   = "${var.role_name}-bedrock-invoke"
  role   = module.role.role_name
  policy = data.aws_iam_policy_document.bedrock_invoke.json
}

data "aws_iam_policy_document" "dynamodb_jobs" {
  count = length(var.dynamodb_table_arns) > 0 ? 1 : 0

  statement {
    sid    = "DynamoDbListTablesForHealthCheck"
    effect = "Allow"
    actions = [
      "dynamodb:ListTables",
    ]
    resources = ["*"]
  }

  statement {
    sid    = "DynamoDbConversionJobs"
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
    resources = concat(
      var.dynamodb_table_arns,
      [for arn in var.dynamodb_table_arns : "${arn}/index/*"],
    )
  }
}

resource "aws_iam_role_policy" "dynamodb_jobs" {
  count = length(var.dynamodb_table_arns) > 0 ? 1 : 0

  name   = "${var.role_name}-dynamodb-jobs"
  role   = module.role.role_name
  policy = data.aws_iam_policy_document.dynamodb_jobs[0].json
}

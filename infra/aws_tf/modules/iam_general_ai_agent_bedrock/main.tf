###############################################################################
# Trust: EKS IRSA (when irsa_trust is set) or same-account root for local dev.
###############################################################################

data "aws_iam_policy_document" "assume_general_ai_agent" {
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
  assume_role_policy_json = data.aws_iam_policy_document.assume_general_ai_agent.json
  description             = "Bedrock Runtime invoke for general.ai.agent.svc (align app_config [agent.bedrock] with TF vars)."
  managed_policy_arns     = []
  additional_tags = {
    "iam:Service" = "general-ai-agent"
  }
}

data "aws_iam_policy_document" "bedrock_invoke" {
  statement {
    sid    = "BedrockConversationAnthropic"
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

locals {
  prefix = "/arb/${var.solution.name}/${var.solution.deployment_key}/services"
  services = {
    frontend = {
      id   = "arb-frontend"
      name = "arb-sherpa-frontend"
    }
    manager_web = {
      id   = "arb-manager-web"
      name = "arb-manager-web"
    }
    iam_svc = {
      id   = "arb-iam-svc"
      name = "arb-iam-svc"
    }
    general_ai_agent_svc = {
      id   = "arb-general-ai-agent-svc"
      name = "arb-general-ai-agent-svc"
    }
    solutions_svc = {
      id   = "arb-solutions-svc"
      name = "arb-solutions-svc"
    }
    storage_svc = {
      id   = "arb-storage-svc"
      name = "arb-storage-svc"
    }
    notification_svc = {
      id   = "arb-notification-svc"
      name = "arb-notification-svc"
    }
    collaboration_svc = {
      id   = "arb-collaboration-svc"
      name = "arb-collaboration-svc"
    }
    document_storage_svc = {
      id   = "arb-document-storage-svc"
      name = "arb-document-storage-svc"
    }
    arch_diagram_agent_svc = {
      id   = "arb-arch-diagram-agent-svc"
      name = "arb-arch-diagram-agent-svc"
    }
    aspire = {
      id   = "arb-aspire"
      name = "arb-aspire-host"
    }
  }
}

resource "aws_cloudwatch_log_group" "service" {
  for_each = local.services

  name              = "${local.prefix}/${each.key}"
  retention_in_days = var.retention_in_days

  tags = {
    "service.id"   = each.value.id
    "service.name" = each.value.name
  }
}

data "aws_iam_policy_document" "application_logs_put" {
  statement {
    sid = "PutApplicationLogs"
    actions = [
      "logs:CreateLogStream",
      "logs:PutLogEvents",
      "logs:DescribeLogStreams",
    ]
    resources = [for g in aws_cloudwatch_log_group.service : "${g.arn}:*"]
  }
}

resource "aws_iam_policy" "application_logs_put" {
  name_prefix = "${var.solution.name}-app-logs-"
  description = "Emit application logs (OpenTelemetry / AWS SDK) to CloudWatch log groups for ${var.solution.name}."
  policy      = data.aws_iam_policy_document.application_logs_put.json

  tags = {
    solution = var.solution.name
  }
}

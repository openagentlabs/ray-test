locals {
  log_prefix = "/arb/${var.solution.name}"

  # Container Insights standard paths (pre-created for retention + tagging).
  container_insights_application = "/aws/containerinsights/${var.cluster_name}/application"
  container_insights_performance = "/aws/containerinsights/${var.cluster_name}/performance"
  container_insights_dataplane     = "/aws/containerinsights/${var.cluster_name}/dataplane"

  # Control plane logs use /aws/eks/{cluster}/cluster (created in eks_platform).
  eks_control_plane_log_group = "/aws/eks/${var.cluster_name}/cluster"
  eks_containers_log_group      = "${local.log_prefix}/eks/${var.cluster_name}/containers"

  addon_configuration = jsonencode({
    agent = {
      config = {
        logs = {
          metrics_collected = {
            kubernetes = {
              cluster_name                = var.cluster_name
              enhanced_container_insights = true
            }
          }
        }
      }
    }
    containerLogs = {
      enabled = true
    }
  })

  # Map Kubernetes workload / Helm release names to application log group suffix keys.
  fargate_log_route_services = {
    frontend             = "frontend"
    iam                  = "iam_svc"
    solutions            = "solutions_svc"
    storage              = "storage_svc"
    notification         = "notification_svc"
    collaboration        = "collaboration_svc"
    document-storage     = "document_storage_svc"
    general-ai-agent     = "general_ai_agent_svc"
    arch-diagram-agent   = "arch_diagram_agent_svc"
  }
}

resource "aws_cloudwatch_log_group" "eks_containers" {
  name              = local.eks_containers_log_group
  retention_in_days = var.retention_in_days

  tags = {
    purpose  = "eks-fargate-containers"
    cluster  = var.cluster_name
    solution = var.solution.name
  }
}

resource "aws_cloudwatch_log_group" "container_insights_application" {
  name              = local.container_insights_application
  retention_in_days = var.retention_in_days

  tags = {
    purpose  = "container-insights-application"
    cluster  = var.cluster_name
    solution = var.solution.name
  }
}

resource "aws_cloudwatch_log_group" "container_insights_performance" {
  name              = local.container_insights_performance
  retention_in_days = var.retention_in_days

  tags = {
    purpose  = "container-insights-performance"
    cluster  = var.cluster_name
    solution = var.solution.name
  }
}

resource "aws_cloudwatch_log_group" "container_insights_dataplane" {
  name              = local.container_insights_dataplane
  retention_in_days = var.retention_in_days

  tags = {
    purpose  = "container-insights-dataplane"
    cluster  = var.cluster_name
    solution = var.solution.name
  }
}

data "aws_iam_policy_document" "observability_assume" {
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
      values = [
        "system:serviceaccount:amazon-cloudwatch:cloudwatch-agent",
        "system:serviceaccount:amazon-cloudwatch:fluent-bit",
      ]
    }
    condition {
      test     = "StringEquals"
      variable = "${var.oidc_provider_url}:aud"
      values   = ["sts.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "cloudwatch_observability" {
  name_prefix        = "${var.solution.name}-eks-cw-obs-"
  assume_role_policy = data.aws_iam_policy_document.observability_assume.json

  tags = {
    purpose = "eks-cloudwatch-observability-irsa"
    cluster = var.cluster_name
  }
}

resource "aws_iam_role_policy_attachment" "cloudwatch_agent_server" {
  role       = aws_iam_role.cloudwatch_observability.name
  policy_arn = "arn:aws:iam::aws:policy/CloudWatchAgentServerPolicy"
}

resource "aws_iam_role_policy_attachment" "cloudwatch_xray_write" {
  role       = aws_iam_role.cloudwatch_observability.name
  policy_arn = "arn:aws:iam::aws:policy/AWSXrayWriteOnlyAccess"
}

data "aws_iam_policy_document" "observability_application_logs" {
  statement {
    sid = "PutEksAndApplicationLogs"
    actions = [
      "logs:CreateLogStream",
      "logs:PutLogEvents",
      "logs:DescribeLogStreams",
      "logs:DescribeLogGroups",
    ]
    resources = concat(
      [
        aws_cloudwatch_log_group.eks_containers.arn,
        "${aws_cloudwatch_log_group.eks_containers.arn}:*",
        aws_cloudwatch_log_group.container_insights_application.arn,
        "${aws_cloudwatch_log_group.container_insights_application.arn}:*",
        aws_cloudwatch_log_group.container_insights_performance.arn,
        "${aws_cloudwatch_log_group.container_insights_performance.arn}:*",
        aws_cloudwatch_log_group.container_insights_dataplane.arn,
        "${aws_cloudwatch_log_group.container_insights_dataplane.arn}:*",
      ],
      flatten([
        for arn in var.application_log_group_arns : [arn, "${arn}:*"]
      ]),
    )
  }
}

resource "aws_iam_role_policy" "observability_application_logs" {
  name_prefix = "${var.solution.name}-eks-cw-logs-"
  role        = aws_iam_role.cloudwatch_observability.id
  policy      = data.aws_iam_policy_document.observability_application_logs.json
}

data "aws_iam_policy_document" "fargate_logging" {
  statement {
    sid = "FargateFluentBitLogs"
    actions = [
      "logs:CreateLogStream",
      "logs:PutLogEvents",
      "logs:DescribeLogStreams",
    ]
    resources = concat(
      [
        aws_cloudwatch_log_group.eks_containers.arn,
        "${aws_cloudwatch_log_group.eks_containers.arn}:*",
        aws_cloudwatch_log_group.container_insights_application.arn,
        "${aws_cloudwatch_log_group.container_insights_application.arn}:*",
      ],
      flatten([
        for arn in var.application_log_group_arns : [arn, "${arn}:*"]
      ]),
    )
  }
}

resource "aws_iam_role_policy" "fargate_logging" {
  name_prefix = "${var.solution.name}-fargate-logs-"
  role        = var.fargate_pod_execution_role_name
  policy      = data.aws_iam_policy_document.fargate_logging.json
}

resource "aws_eks_fargate_profile" "amazon_cloudwatch" {
  cluster_name           = var.cluster_name
  fargate_profile_name   = "amazon-cloudwatch"
  pod_execution_role_arn = var.fargate_pod_execution_role_arn
  subnet_ids             = var.subnet_ids

  selector {
    namespace = "amazon-cloudwatch"
  }

  tags = {
    purpose = "eks-fargate-cloudwatch-addon"
  }
}

resource "aws_eks_fargate_profile" "aws_observability" {
  cluster_name           = var.cluster_name
  fargate_profile_name   = "aws-observability"
  pod_execution_role_arn = var.fargate_pod_execution_role_arn
  subnet_ids             = var.subnet_ids

  selector {
    namespace = "aws-observability"
  }

  tags = {
    purpose = "eks-fargate-logging-config"
  }
}

resource "aws_eks_addon" "cloudwatch_observability" {
  cluster_name                = var.cluster_name
  addon_name                  = "amazon-cloudwatch-observability"
  resolve_conflicts_on_create = "OVERWRITE"
  resolve_conflicts_on_update = "OVERWRITE"
  configuration_values        = local.addon_configuration
  service_account_role_arn    = aws_iam_role.cloudwatch_observability.arn

  depends_on = [
    aws_eks_fargate_profile.amazon_cloudwatch,
    aws_iam_role_policy_attachment.cloudwatch_agent_server,
  ]
}

resource "kubernetes_namespace" "aws_observability" {
  provider = kubernetes

  metadata {
    name = "aws-observability"
    labels = {
      "app.kubernetes.io/managed-by" = "terraform"
      solution                         = var.solution.name
    }
  }
}

resource "kubernetes_config_map" "aws_logging" {
  provider = kubernetes

  metadata {
    name      = "aws-logging"
    namespace = kubernetes_namespace.aws_observability.metadata[0].name
  }

  data = {
    "filters.conf" = <<-EOT
      [FILTER]
          Name parser
          Match *
          Key_name log
          Parser crio
      [FILTER]
          Name kubernetes
          Match kube.*
          Merge_Log On
          Keep_Log Off
          K8S-Logging.Parser On
          K8S-Logging.Exclude Off
    EOT

    "output.conf" = join("\n", concat(
      [
        <<-EOT
          [OUTPUT]
              Name cloudwatch_logs
              Match *
              region ${var.solution.region}
              log_group_name ${local.eks_containers_log_group}
              log_stream_prefix fargate-
              auto_create_group false
        EOT
      ],
      [
        for release, service_key in local.fargate_log_route_services :
        <<-EOT
          [OUTPUT]
              Name cloudwatch_logs
              Match kube.*${release}*
              region ${var.solution.region}
              log_group_name ${lookup(var.application_log_group_names, service_key, local.eks_containers_log_group)}
              log_stream_prefix ${release}-
              auto_create_group false
        EOT
      ],
    ))
  }

  depends_on = [
    aws_eks_fargate_profile.aws_observability,
    kubernetes_namespace.aws_observability,
  ]
}

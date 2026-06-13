# MIDAS observability-fluent-bit Terraform module
#
# Deploys aws-for-fluent-bit as a Kubernetes DaemonSet in kube-system.
# One Fluent Bit pod per node tails /var/log/containers/*.log and ships
# logs from the midas-apps namespace to CloudWatch Logs.
#
# Prerequisites (already in place — no changes needed here):
#   - IAM inline policy node_cloudwatch_logs on the EKS node role grants
#     logs:PutLogEvents on arn:aws:logs:us-east-1:*:log-group:/midas/*
#     (deploy/ecs-app/modules/eks/main.tf)
#   - CloudWatch Log Group /midas/<environment>/backend is Terraform-managed
#     (deploy/ecs-app/modules/observability-app-logs/main.tf)
#
# Image mirroring:
#   The VPC has no NAT/IGW so nodes cannot pull from public.ecr.aws.
#   The image must be mirrored to the private ECR repo created below before
#   the first apply.  Mirror command (run once per version bump):
#
#     SOURCE=public.ecr.aws/aws-observability/aws-for-fluent-bit:<version>
#     DEST=<account>.dkr.ecr.us-east-1.amazonaws.com/midas-<env>-aws-for-fluent-bit:<version>
#     aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <account>.dkr.ecr.us-east-1.amazonaws.com
#     docker pull $SOURCE && docker tag $SOURCE $DEST && docker push $DEST
#
#   This is consistent with the aws-load-balancer-controller ECR mirror pattern
#   (deploy/ecs-app/eks-alb-controller-helm.tf).

locals {
  ecr_repo_name = "midas-${var.environment}-aws-for-fluent-bit"
  image_url     = "${var.aws_account_id}.dkr.ecr.${var.aws_region}.amazonaws.com/${local.ecr_repo_name}"
}

# Fortify "Insecure ECR Storage": customer-managed KMS key for ECR image encryption.
resource "aws_kms_key" "fluent_bit_ecr" {
  description             = "MIDAS Fluent Bit ECR encryption — ${local.ecr_repo_name}"
  deletion_window_in_days = 30
  enable_key_rotation     = true

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "AllowAccountRoot"
        Effect    = "Allow"
        Principal = { AWS = "arn:aws:iam::${var.aws_account_id}:root" }
        Action    = "kms:*"
        Resource  = "*"
      }
    ]
  })

  tags = merge(
    {
      Environment = var.environment
      ManagedBy   = "terraform"
      Project     = "midas"
      Component   = "observability-fluent-bit"
    },
    var.tags,
  )
}

resource "aws_kms_alias" "fluent_bit_ecr" {
  name          = "alias/${local.ecr_repo_name}-ecr"
  target_key_id = aws_kms_key.fluent_bit_ecr.key_id
}

# Private ECR repository for the Fluent Bit image mirror.
resource "aws_ecr_repository" "fluent_bit" {
  name                 = local.ecr_repo_name
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  encryption_configuration {
    encryption_type = "KMS"
    kms_key         = aws_kms_key.fluent_bit_ecr.arn
  }

  tags = merge(
    {
      Environment = var.environment
      ManagedBy   = "terraform"
      Project     = "midas"
      Component   = "observability-fluent-bit"
    },
    var.tags,
  )

  # ECR does not support in-place encryption-type changes. The existing
  # repository (created without an encryption_configuration, i.e. AES256)
  # stays on AES256 via this ignore_changes; *new* deployments of this module
  # will be KMS-encrypted from the start.
  lifecycle {
    ignore_changes = [encryption_configuration]
  }
}

# Fortify "Improper ECR Access Control" remediation: resource-based policy that
# explicitly allows same-account principals (Jenkins, EKS nodes) and denies any
# cross-account access. IAM identity policies continue to provide the primary
# access control; this policy is defense-in-depth.
data "aws_iam_policy_document" "fluent_bit_ecr_repo_policy" {
  statement {
    sid    = "AllowSameAccountPullPush"
    effect = "Allow"
    principals {
      type        = "AWS"
      identifiers = ["arn:aws:iam::${var.aws_account_id}:root"]
    }
    actions = [
      "ecr:GetDownloadUrlForLayer",
      "ecr:BatchGetImage",
      "ecr:BatchCheckLayerAvailability",
      "ecr:PutImage",
      "ecr:InitiateLayerUpload",
      "ecr:UploadLayerPart",
      "ecr:CompleteLayerUpload",
      "ecr:DescribeImages",
      "ecr:ListImages",
      "ecr:DescribeRepositories",
      "ecr:GetRepositoryPolicy",
    ]
  }

  statement {
    sid    = "DenyCrossAccount"
    effect = "Deny"
    principals {
      type        = "AWS"
      identifiers = ["*"]
    }
    actions = ["ecr:*"]
    condition {
      test     = "StringNotEquals"
      variable = "aws:PrincipalAccount"
      values   = [var.aws_account_id]
    }
  }
}

resource "aws_ecr_repository_policy" "fluent_bit" {
  repository = aws_ecr_repository.fluent_bit.name
  policy     = data.aws_iam_policy_document.fluent_bit_ecr_repo_policy.json
}

# Fluent Bit DaemonSet deployed via Helm.
# Uses the hashicorp/helm provider already configured in
# deploy/ecs-app/eks-alb-controller-helm.tf (provider "helm" block).
resource "helm_release" "fluent_bit" {
  name             = "aws-for-fluent-bit"
  repository       = "https://aws.github.io/eks-charts"
  chart            = "aws-for-fluent-bit"
  version          = var.chart_version
  namespace        = "kube-system"
  create_namespace = false

  # Do not block terraform apply waiting for DaemonSet pods to become Ready.
  # DaemonSet rollout is monitored separately after the pipeline completes.
  wait = false

  # ---------------------------------------------------------------------------
  # cloudWatchLogs output — the active plugin in chart >= 0.1.x
  # (cloudWatch = legacy plugin, disabled by default; cloudWatchLogs = new,
  # enabled by default but pointing at /aws/eks/fluentbit-cloudwatch/logs)
  # We override the active cloudWatchLogs plugin to target our log group.
  # ---------------------------------------------------------------------------
  set {
    name  = "cloudWatchLogs.enabled"
    value = "true"
  }

  set {
    name  = "cloudWatchLogs.region"
    value = var.aws_region
  }

  set {
    name  = "cloudWatchLogs.logGroupName"
    value = var.log_group_name
  }

  # Stream per pod: pod/<pod-name> so individual replica logs are addressable.
  set {
    name  = "cloudWatchLogs.logStreamPrefix"
    value = "pod/"
  }

  # The log group is Terraform-managed — do not let Fluent Bit create it.
  set {
    name  = "cloudWatchLogs.autoCreateGroup"
    value = "false"
  }

  # Match the actual tag format produced by Fluent Bit's kubernetes enrichment
  # filter: kube.var.log.containers.<pod>_<namespace>_<container>-<hash>.log
  # The previous value "kube.midas-apps.*" never matched any real tags, which
  # is why no logs appeared in CloudWatch after the last deployment.
  # Namespace restriction is enforced by the grep additionalFilters block below.
  set {
    name  = "cloudWatchLogs.match"
    value = "kube.var.log.containers.*"
  }

  # Disable the legacy cloudWatch plugin (off by default, be explicit).
  set {
    name  = "cloudWatch.enabled"
    value = "false"
  }

  # ---------------------------------------------------------------------------
  # Namespace filter — only forward logs from the midas-apps namespace.
  # Without this, every pod on every node (kube-system, etc.) would be shipped.
  # The kubernetes enrichment filter adds $kubernetes['namespace_name'] to each
  # record; we grep for exactly "midas-apps" to discard all other namespaces.
  # ---------------------------------------------------------------------------
  set {
    name  = "additionalFilters"
    value = "[FILTER]\n    Name   grep\n    Match  kube.var.log.containers.*\n    Regex  $kubernetes['namespace_name'] ^midas-apps$\n"
  }

  # ---------------------------------------------------------------------------
  # Disable unused outputs
  # ---------------------------------------------------------------------------
  set {
    name  = "firehose.enabled"
    value = "false"
  }

  set {
    name  = "kinesis.enabled"
    value = "false"
  }

  set {
    name  = "elasticsearch.enabled"
    value = "false"
  }

  # ---------------------------------------------------------------------------
  # Private ECR image — required because nodes have no internet egress.
  # Image must be mirrored to the ECR repo created above before first apply.
  # ---------------------------------------------------------------------------
  set {
    name  = "image.repository"
    value = local.image_url
  }

  # ---------------------------------------------------------------------------
  # How tags flow:
  #   INPUT (tail)  → tags each file as: kube.var.log.containers.<file>.log
  #   FILTER (k8s)  → enriches records with kubernetes.namespace_name, etc.
  #   FILTER (grep) → above additionalFilters drops non-midas-apps records
  #   OUTPUT (cwl)  → only matching records reach /midas/<env>/backend
  # ---------------------------------------------------------------------------

  depends_on = [aws_ecr_repository.fluent_bit]
}

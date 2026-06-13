# MIDAS observability-cloudwatch-agent Terraform module
#
# Deploys the AWS amazon-cloudwatch-observability Helm chart, which installs:
#   - The CloudWatch Agent as a DaemonSet (one pod per node) in the
#     amazon-cloudwatch namespace.
#   - The amazon-cloudwatch-observability operator Deployment that manages
#     the agent's CRD-driven lifecycle.
#
# Outcome:
#   The agent emits node, pod, and container metrics to CloudWatch under
#   namespace ContainerInsights (cluster_name dimension = var.eks_cluster_name).
#   This includes node_memory_utilization, node_memory_working_set,
#   pod_memory_utilization, and similar memory series for every EC2 worker.
#   Visible in the CloudWatch console under:
#     CloudWatch -> Insights -> Container Insights -> midas-eks-<env>
#
# Non-disruptive rollout:
#   The chart only adds DaemonSet pods to existing nodes and a small operator
#   Deployment. No AMI change, no managed node-group rolling update, no EC2
#   replacement. See deploy/EKS_NODEGROUP_AND_HELM_RESOURCES_PLAN.md for the
#   backend Guaranteed-QoS sizing that leaves slack on each m6i.4xlarge for
#   kube-system DaemonSets like this one.
#
# Permissions (least privilege via IRSA, not on the node role):
#   - This module creates a dedicated IAM role assumed by the
#     cloudwatch-agent service account in the amazon-cloudwatch namespace
#     (sts:AssumeRoleWithWebIdentity through the existing EKS OIDC provider).
#   - The AWS-managed policy CloudWatchAgentServerPolicy is attached to that
#     role, granting cloudwatch:PutMetricData, logs:PutLogEvents, ec2:Describe*
#     and ssm:GetParameter on AmazonCloudWatch-* parameters.
#   - The EKS node role is intentionally NOT modified, so the existing
#     MIDAS/Training namespace restriction in
#     deploy/ecs-app/eks-node-cloudwatch-metrics.tf stays intact.
#
# Image mirror (no NAT/IGW, so public.ecr.aws is unreachable from nodes):
#   The two container images are mirrored to private ECR by
#   deploy/scripts/ci/mirror-addon-images-ecr.sh before the first apply.
#   Tags must stay in sync with var.agent_image_tag and var.operator_image_tag.
#
# Related:
#   - deploy/ecs-app/modules/observability-fluent-bit/main.tf (sibling pattern)
#   - deploy/ecs-app/eks-alb-controller-helm.tf            (helm provider)
#   - deploy/ecs-app/eks-alb-controller.tf                 (OIDC provider)
#   - deploy/ecs-app/eks-node-cloudwatch-metrics.tf        (training metric IAM)

locals {
  ecr_repo_name_agent    = "midas-${var.environment}-cloudwatch-agent"
  ecr_repo_name_operator = "midas-${var.environment}-cloudwatch-agent-operator"

  private_registry = "${var.aws_account_id}.dkr.ecr.${var.aws_region}.amazonaws.com"

  # The CloudWatch Agent and operator images are pulled from these full URIs
  # (registry/repo:tag) at pod start. Built from the mirrored ECR repo URLs.
  agent_image_uri    = "${local.private_registry}/${local.ecr_repo_name_agent}:${var.agent_image_tag}"
  operator_image_uri = "${local.private_registry}/${local.ecr_repo_name_operator}:${var.operator_image_tag}"

  oidc_issuer_host_path = replace(var.oidc_issuer_url, "https://", "")

  common_tags = merge(
    {
      Environment = var.environment
      ManagedBy   = "terraform"
      Project     = "midas"
      Component   = "observability-cloudwatch-agent"
    },
    var.tags,
  )
}

# ---------------------------------------------------------------------------
# Private ECR repositories for the CloudWatch Agent and its operator.
# Same lifecycle and tagging as the fluent-bit mirror repo.
# ---------------------------------------------------------------------------
resource "aws_ecr_repository" "cwagent" {
  name                 = local.ecr_repo_name_agent
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = local.common_tags
}

resource "aws_ecr_repository" "cwagent_operator" {
  name                 = local.ecr_repo_name_operator
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = local.common_tags
}

# ---------------------------------------------------------------------------
# IRSA role assumed by the cloudwatch-agent service account.
#
# Naming follows the existing pattern (midas-eks-<env>-<service>) so the
# midas-deployer-role IAM grant in deploy/deploy_role/iam-policy/midas-deployer-policy-006
# (IamForEksRoles, Resource arn:aws:iam::*:role/midas-eks-*) covers this role
# without changing the deployer policy set.
# ---------------------------------------------------------------------------
resource "aws_iam_role" "cwagent" {
  name = "${var.eks_cluster_name}-cloudwatch-agent"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Federated = var.oidc_provider_arn
      }
      Action = "sts:AssumeRoleWithWebIdentity"
      Condition = {
        StringEquals = {
          "${local.oidc_issuer_host_path}:aud" = "sts.amazonaws.com"
          "${local.oidc_issuer_host_path}:sub" = "system:serviceaccount:${var.kubernetes_namespace}:${var.agent_service_account_name}"
        }
      }
    }]
  })

  tags = local.common_tags
}

# Attach the AWS-managed policy for the CloudWatch Agent. This is the official
# permission set documented at:
#   https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/install-CloudWatch-Agent-on-EKS-fargate.html
# Actions (summary): cloudwatch:PutMetricData, ec2:DescribeVolumes,
# ec2:DescribeTags, logs:PutLogEvents, logs:DescribeLogStreams,
# logs:DescribeLogGroups, logs:CreateLogStream, logs:CreateLogGroup,
# ssm:GetParameter on AmazonCloudWatch-*.
resource "aws_iam_role_policy_attachment" "cwagent_server_policy" {
  role       = aws_iam_role.cwagent.name
  policy_arn = "arn:aws:iam::aws:policy/CloudWatchAgentServerPolicy"
}

# ---------------------------------------------------------------------------
# Helm release of the amazon-cloudwatch-observability chart.
#
# The chart defaults install the Container Insights "enhanced observability"
# preset (per-pod and per-container metrics, including memory). We do NOT
# override agent.config so the default preset is used.
#
# We DO override:
#   - clusterName / region    : required by the agent.
#   - image URIs              : point at private ECR (no NAT/IGW from nodes).
#   - agent.serviceAccount.name : the SA name the chart creates (we patch the
#                               IRSA annotation on that SA below — the chart's
#                               cloudwatch-agent-serviceaccount.yaml template
#                               does NOT support annotations).
#   - containerLogs.enabled   : false to avoid a duplicate Fluent Bit pipeline
#                               (MIDAS already runs aws-for-fluent-bit).
# ---------------------------------------------------------------------------
resource "helm_release" "cloudwatch_observability" {
  name             = "amazon-cloudwatch-observability"
  repository       = "https://aws-observability.github.io/helm-charts"
  chart            = "amazon-cloudwatch-observability"
  version          = var.chart_version
  namespace        = var.kubernetes_namespace
  create_namespace = true

  # wait = true so we block until the operator Deployment is Ready. The
  # kubernetes_annotations resource below then patches the cloudwatch-agent SA
  # before the operator's reconcile loop has had time to spawn long-lived
  # DaemonSet pods. Any pods that did start are restarted by the null_resource
  # below.
  wait    = true
  timeout = 600

  set {
    name  = "clusterName"
    value = var.eks_cluster_name
  }

  set {
    name  = "region"
    value = var.aws_region
  }

  # CloudWatch Agent image - mirrored to private ECR.
  # Chart 4.x resolves the image URL as repositoryDomainMap[region]/repository:tag
  # and falls back to repositoryDomainMap.public when region is not in the map
  # (us-east-1 is not in the chart defaults). We override the .public fallback
  # so nodes pull from private ECR instead of public.ecr.aws (no NAT/IGW).
  set {
    name  = "agent.image.repositoryDomainMap.public"
    value = local.private_registry
  }

  set {
    name  = "agent.image.repository"
    value = local.ecr_repo_name_agent
  }

  set {
    name  = "agent.image.tag"
    value = var.agent_image_tag
  }

  # Pin the SA name the chart creates so we can find it for the IRSA patch
  # below. The chart's serviceAccount template only honours .name (it does
  # NOT render annotations), so we cannot inject IRSA via helm_release.set —
  # see kubernetes_annotations.cwagent_irsa.
  set {
    name  = "agent.serviceAccount.name"
    value = var.agent_service_account_name
  }

  # Operator (amazon-cloudwatch-observability-controller-manager) image -
  # mirrored to private ECR. Same repositoryDomainMap pattern as the agent
  # (see comment above).
  set {
    name  = "manager.image.repositoryDomainMap.public"
    value = local.private_registry
  }

  set {
    name  = "manager.image.repository"
    value = local.ecr_repo_name_operator
  }

  set {
    name  = "manager.image.tag"
    value = var.operator_image_tag
  }

  # Disable the chart's bundled Fluent Bit. MIDAS already ships container
  # stdout to CloudWatch Logs via deploy/ecs-app/modules/observability-fluent-bit.
  # Running both would duplicate log lines and double the log ingest cost.
  set {
    name  = "containerLogs.enabled"
    value = var.container_logs_enabled ? "true" : "false"
  }

  depends_on = [
    aws_ecr_repository.cwagent,
    aws_ecr_repository.cwagent_operator,
    aws_iam_role_policy_attachment.cwagent_server_policy,
  ]
}

# ---------------------------------------------------------------------------
# IRSA annotation patch on the cloudwatch-agent ServiceAccount.
#
# Why this is required:
#   - The amazon-cloudwatch-observability chart's
#     templates/cloudwatch-agent-serviceaccount.yaml renders the SA with only
#     `metadata.name` and `metadata.namespace` — it has no values path for
#     annotations. Setting agent.serviceAccount.annotations.* in helm_release
#     is silently ignored.
#   - Without the eks.amazonaws.com/role-arn annotation, the EKS pod-identity
#     mutating webhook does NOT inject AWS_ROLE_ARN / AWS_WEB_IDENTITY_TOKEN_FILE
#     into agent pods. The agent then falls back to the node IAM role, which
#     in MIDAS is scoped to namespace MIDAS/Training and /midas/* log groups
#     only — so PutMetricData to "ContainerInsights" and PutLogEvents to
#     /aws/containerinsights/<cluster>/performance are both denied.
#
# force = true so terraform owns this annotation across drift.
# ---------------------------------------------------------------------------
resource "kubernetes_annotations" "cwagent_irsa" {
  api_version = "v1"
  kind        = "ServiceAccount"
  metadata {
    name      = var.agent_service_account_name
    namespace = var.kubernetes_namespace
  }

  annotations = {
    "eks.amazonaws.com/role-arn" = aws_iam_role.cwagent.arn
  }

  force = true

  depends_on = [helm_release.cloudwatch_observability]
}

# ---------------------------------------------------------------------------
# Rollout-restart the cloudwatch-agent DaemonSet after the SA is annotated.
#
# The operator reconciles the AmazonCloudWatchAgent CR and creates the
# DaemonSet a few seconds after Helm install. If those pods were created
# before kubernetes_annotations.cwagent_irsa patched the SA, they will be
# running without the projected service-account token volume and the
# AWS_ROLE_ARN env var, so they will keep using the node role and fail to
# write to CloudWatch.
#
# This null_resource waits up to 5 minutes for the DaemonSet to appear,
# rollout-restarts it, then waits for the rollout to complete. The triggers
# block re-runs the provisioner whenever the IRSA role ARN changes.
#
# Requirements on the apply host (Jenkins agent already satisfies all):
#   - aws CLI (for `aws eks update-kubeconfig`)
#   - kubectl
#   - IAM principal allowed to call eks:DescribeCluster on midas-eks-<env>
#     (the Jenkins deployer role already has this).
# ---------------------------------------------------------------------------
resource "null_resource" "cwagent_rollout_restart" {
  triggers = {
    role_arn        = aws_iam_role.cwagent.arn
    cluster_name    = var.eks_cluster_name
    namespace       = var.kubernetes_namespace
    agent_image_tag = var.agent_image_tag
  }

  provisioner "local-exec" {
    interpreter = ["bash", "-c"]
    command     = <<-EOT
      set -euo pipefail

      KCFG="$(mktemp)"
      trap 'rm -f "$KCFG"' EXIT

      aws eks update-kubeconfig \
        --name "${var.eks_cluster_name}" \
        --region "${var.aws_region}" \
        --kubeconfig "$KCFG" >/dev/null

      # Wait up to 5 minutes for the operator to reconcile the
      # AmazonCloudWatchAgent CR and create the DaemonSet.
      for i in $(seq 1 60); do
        if kubectl --kubeconfig "$KCFG" -n "${var.kubernetes_namespace}" \
            get daemonset cloudwatch-agent >/dev/null 2>&1; then
          break
        fi
        sleep 5
      done

      if ! kubectl --kubeconfig "$KCFG" -n "${var.kubernetes_namespace}" \
          get daemonset cloudwatch-agent >/dev/null 2>&1; then
        echo "cloudwatch-agent DaemonSet did not appear within 5 minutes; new pods will still pick up IRSA when the operator creates them."
        exit 0
      fi

      kubectl --kubeconfig "$KCFG" -n "${var.kubernetes_namespace}" \
        rollout restart daemonset cloudwatch-agent

      kubectl --kubeconfig "$KCFG" -n "${var.kubernetes_namespace}" \
        rollout status daemonset cloudwatch-agent --timeout=5m || true
    EOT
  }

  depends_on = [kubernetes_annotations.cwagent_irsa]
}

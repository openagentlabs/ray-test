# -----------------------------------------------------------------------------
# Observability: backend application CloudWatch Log Group
# Creates /midas/<environment>/backend — exported so helm-deploy-releases.sh
# can inject it as observability.logGroupName (LOG_CLOUDWATCH_LOG_GROUP) into
# the backend pod environment.  See docs/observability-configuration.md.
# -----------------------------------------------------------------------------

module "observability_app_logs" {
  source = "./modules/observability-app-logs"

  environment       = var.environment
  retention_in_days = var.observability_log_retention_days
  kms_key_arn       = var.observability_kms_key_arn
}

# -----------------------------------------------------------------------------
# Observability: Amazon Managed Prometheus (AMP) workspace (Phase B)
# Enabled when observability_amp_enabled = true (default false — safe to skip
# until the ADOT Collector DaemonSet is ready to be deployed).
# See docs/adr/0001-midas-amp-amg-observability.md.
# -----------------------------------------------------------------------------

module "observability_amp" {
  count  = var.observability_amp_enabled ? 1 : 0
  source = "./modules/observability-amp"

  environment        = var.environment
  eks_node_role_name = var.observability_amp_enabled ? module.eks.eks_node_role_name : ""
  retention_in_days  = var.observability_log_retention_days
}

# -----------------------------------------------------------------------------
# Observability: Fluent Bit DaemonSet — CloudWatch Log Shipping (Phase A)
# Ships container stdout logs from midas-apps namespace to CloudWatch Logs at
# /midas/<environment>/backend.  Enabled when observability_fluent_bit_enabled
# = true (default false).
#
# The EKS node IAM role already has logs:PutLogEvents on /midas/* (added in
# deploy/ecs-app/modules/eks/main.tf) — no extra IAM work needed here.
#
# Image pre-requisite: mirror public.ecr.aws/aws-observability/aws-for-fluent-bit
# to the private ECR repo created by this module before the first apply.
# See deploy/ecs-app/modules/observability-fluent-bit/main.tf for the command.
# -----------------------------------------------------------------------------

module "observability_fluent_bit" {
  count  = var.observability_fluent_bit_enabled ? 1 : 0
  source = "./modules/observability-fluent-bit"

  environment      = var.environment
  aws_region       = var.aws_region
  aws_account_id   = var.aws_account_id
  eks_cluster_name = module.eks.eks_cluster_name
  # Helm provider uses exec authenticator — cluster endpoint and CA must be
  # passed so the module's helm_release uses the correct kubeconfig context.
  eks_cluster_endpoint = module.eks.eks_cluster_endpoint
  eks_cluster_ca       = module.eks.eks_cluster_certificate_authority_data
  log_group_name       = module.observability_app_logs.backend_application_log_group_name
}

# -----------------------------------------------------------------------------
# Observability: amazon-cloudwatch-observability (CloudWatch Container Insights)
# Deploys the CloudWatch Agent DaemonSet + operator in the amazon-cloudwatch
# namespace. Emits node, pod, and container metrics (incl. node_memory_*,
# pod_memory_utilization) to CloudWatch under namespace ContainerInsights.
#
# Enabled when observability_cloudwatch_agent_enabled = true (default false,
# enabled in dev tfvars only). Adds DaemonSet pods to existing nodes; does
# NOT roll the managed node group and does NOT replace EC2 workers.
#
# Image pre-requisite: cloudwatch-agent and cloudwatch-agent-operator must
# be mirrored to private ECR before the first apply (no NAT/IGW in VPC).
# See deploy/scripts/ci/mirror-addon-images-ecr.sh.
#
# Permissions: a dedicated IRSA role
# (midas-eks-<env>-cloudwatch-agent) is created with the AWS-managed
# CloudWatchAgentServerPolicy. The EKS node role is NOT modified, so the
# existing MIDAS/Training namespace condition stays intact.
# -----------------------------------------------------------------------------

module "observability_cloudwatch_agent" {
  count  = var.observability_cloudwatch_agent_enabled ? 1 : 0
  source = "./modules/observability-cloudwatch-agent"

  environment      = var.environment
  aws_region       = var.aws_region
  aws_account_id   = var.aws_account_id
  eks_cluster_name = module.eks.eks_cluster_name
  # Helm provider exec auth: cluster endpoint + CA flow through the module
  # for consistency with observability-fluent-bit (the provider itself is
  # configured once in deploy/ecs-app/eks-alb-controller-helm.tf).
  eks_cluster_endpoint = module.eks.eks_cluster_endpoint
  eks_cluster_ca       = module.eks.eks_cluster_certificate_authority_data
  oidc_provider_arn    = module.eks_alb_controller_iam.oidc_provider_arn
  oidc_issuer_url      = module.eks.oidc_issuer_url
}

# -----------------------------------------------------------------------------
# Observability: Amazon OpenSearch Service domain (Phase C — KQL log search)
# Enabled when observability_opensearch_enabled = true (default false — safe
# to skip until Fluent Bit dual-write is configured).
# See docs/adr/0002-midas-kql-log-search.md.
# -----------------------------------------------------------------------------

module "observability_opensearch" {
  count  = var.observability_opensearch_enabled ? 1 : 0
  source = "./modules/observability-opensearch"

  environment        = var.environment
  vpc_id             = var.eks_vpc_id
  subnet_ids         = var.eks_node_subnet_ids
  master_user_arn    = module.eks.eks_node_role_arn
  eks_node_role_name = module.eks.eks_node_role_name
  retention_in_days  = var.observability_log_retention_days
}

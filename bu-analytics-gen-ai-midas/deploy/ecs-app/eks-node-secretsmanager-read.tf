# -----------------------------------------------------------------------------
# Inline IAM on the EKS worker node role: Secrets Manager read for app startup.
# Pods (e.g. midas-api-backend) use the node role via the default credential chain
# and call secretsmanager:GetSecretValue for RDS/ElastiCache, the midas app secret, and optional extras.
# If pods still get AccessDenied with this policy present, check org SCPs and any Secrets Manager VPC
# interface endpoint policy (endpoint policies can deny even when IAM allows).
# Prefer IRSA later for a smaller blast radius than widening the node role.
# This file lives in the ecs-app root (not module.eks) to avoid a Terraform cycle:
# module.rds_postgres depends on module.eks for the cluster security group.
# -----------------------------------------------------------------------------

locals {
  # compact() drops "" but not null; use try + compact per optional module output.
  eks_node_secret_arns_base = concat(
    var.rds_postgres_enabled ? compact([try(module.rds_postgres[0].db_master_user_secret_arn, "")]) : [],
    var.elasticache_redis_enabled ? compact([try(module.elasticache_redis[0].redis_auth_secret_arn, "")]) : [],
    compact(var.eks_node_extra_secretsmanager_secret_arns),
    # App secret JSON is usually injected via K8s env, but slots (S3/Bedrock) may still call SM by id; allow reads.
    [module.secretsmanager.app_secret_arn],
  )
  # Secrets Manager ARNs end with a random 6-character suffix; IAM is most reliable when the Resource
  # includes both the full ARN from Terraform and the same logical secret as "name-*" (AWS IAM docs).
  eks_node_secretsmanager_resources = distinct(concat(
    compact(local.eks_node_secret_arns_base),
    [for arn in compact(local.eks_node_secret_arns_base) : replace(arn, "/-[A-Za-z0-9]{6}$/", "-*")],
  ))
}

resource "aws_iam_role_policy" "eks_node_secretsmanager_read" {
  count = length(local.eks_node_secretsmanager_resources) > 0 ? 1 : 0
  name  = "${module.eks.eks_cluster_name}-node-secretsmanager-read"
  role  = module.eks.eks_node_role_name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "SecretsManagerReadForWorkloadPods"
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue",
          "secretsmanager:DescribeSecret",
        ]
        Resource = local.eks_node_secretsmanager_resources
      },
    ]
  })
}

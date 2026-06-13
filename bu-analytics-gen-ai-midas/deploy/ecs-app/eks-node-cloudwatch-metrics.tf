# -----------------------------------------------------------------------------
# Inline IAM on the EKS worker node role: CloudWatch custom metrics write.
#
# Why this is needed:
#   Backend pods (midas-api-backend) use the aws-embedded-metrics Python library
#   to emit EMF JSON to stdout.  The CloudWatch Logs agent on each node picks up
#   stdout and writes it to the log group — that part uses logs:PutLogEvents (already
#   allowed by the node agent's own role).
#
#   However, for direct boto3 PutMetricData calls (future use), or if the EMF
#   library is configured to push directly rather than via logs, the pod needs
#   cloudwatch:PutMetricData.  Adding it now avoids a blocked deploy later.
#
# Scope constraint:
#   The condition restricts writes to the MIDAS/Training namespace only, so even if
#   other pods on the same node inherit this role they cannot pollute other namespaces.
#
# Note on IRSA:
#   The current pattern (all pods use the node role) is in use across this repo.
#   Migrating to IRSA (per-pod SA with a dedicated role) is the best-practice next
#   step — see deploy/ecs-app/eks-node-secretsmanager-read.tf for the precedent.
#   This file follows the same inline-policy-on-node-role pattern to stay consistent.
#
# Deployment path: Jenkins → terraform apply (never run locally against shared envs).
# Related: deploy/ecs-app/cloudwatch-metrics.tf (log group, metric filter, alarm)
#          backend/app/services/keith_log_matrics_test.py (EMF emit code)
# -----------------------------------------------------------------------------

resource "aws_iam_role_policy" "eks_node_cloudwatch_metrics_write" {
  name = "${module.eks.eks_cluster_name}-node-cloudwatch-metrics-write"
  role = module.eks.eks_node_role_name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "CloudWatchPutMetricDataMidasTraining"
        Effect = "Allow"
        Action = ["cloudwatch:PutMetricData"]
        # cloudwatch:PutMetricData does not support resource-level ARNs —
        # the Resource must be "*".  The namespace condition below provides
        # the scope constraint that IAM cannot express via Resource for this API.
        Resource = "*"
        Condition = {
          StringEquals = {
            "cloudwatch:namespace" = "MIDAS/Training"
            "aws:RequestedRegion"  = "us-east-1"
          }
        }
      },
      {
        Sid    = "CloudWatchLogsWriteMidasApp"
        Effect = "Allow"
        Action = [
          "logs:CreateLogStream",
          "logs:PutLogEvents",
          "logs:DescribeLogStreams",
        ]
        # Scoped to the MIDAS application log group created in cloudwatch-metrics.tf.
        Resource = [
          "arn:aws:logs:us-east-1:*:log-group:/midas/${var.environment}/backend",
          "arn:aws:logs:us-east-1:*:log-group:/midas/${var.environment}/backend:*",
        ]
      },
    ]
  })
}

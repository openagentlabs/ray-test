# -----------------------------------------------------------------------------
# IRSA for the midas-ec2-mt-test-svc Kubernetes Job.
#
# The Job pod uploads the run_batch.py data/ output to
# s3://keith-bucket-test-001/results/ after training completes.
# IRSA (IAM Roles for Service Accounts) provides the pod with scoped
# S3 write credentials without storing keys in the image or Secrets Manager.
#
# Pattern mirrors deploy/ecs-app/eks-alb-controller.tf (OIDC + inline policy +
# IRSA role). No new module is introduced; the OIDC provider created by
# module.eks_alb_controller_iam is reused via its arn output.
# -----------------------------------------------------------------------------

# IAM policy: allow the Job pod to write to the results prefix only.
resource "aws_iam_policy" "ec2_mt_test_s3_results" {
  name        = "midas-${var.environment}-ec2-mt-test-s3-results"
  description = "Allows the midas-ec2-mt-test-svc Job pod to upload batch run output to s3://keith-bucket-test-001/results/."

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "S3ResultsBucketList"
        Effect = "Allow"
        Action = [
          "s3:ListBucket",
          "s3:GetBucketLocation"
        ]
        Resource = "arn:aws:s3:::keith-bucket-test-001"
        Condition = {
          StringLike = {
            "s3:prefix" = ["results/*"]
          }
        }
      },
      {
        Sid    = "S3ResultsObjects"
        Effect = "Allow"
        Action = [
          "s3:PutObject",
          "s3:GetObject",
          "s3:DeleteObject",
          "s3:AbortMultipartUpload",
          "s3:GetObjectTagging",
          "s3:PutObjectTagging"
        ]
        Resource = "arn:aws:s3:::keith-bucket-test-001/results/*"
      }
    ]
  })

  tags = {
    Environment = var.environment
    ManagedBy   = "terraform"
    Project     = "midas-eks"
  }
}

# IRSA role: trusted by the EKS OIDC provider, scoped to the
# midas-ec2-mt-test-sa ServiceAccount in the midas-apps namespace.
resource "aws_iam_role" "ec2_mt_test" {
  name = "midas-${var.environment}-ec2-mt-test-irsa"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Federated = module.eks_alb_controller_iam.oidc_provider_arn
      }
      Action = "sts:AssumeRoleWithWebIdentity"
      Condition = {
        StringEquals = {
          "${replace(module.eks.oidc_issuer_url, "https://", "")}:aud" = "sts.amazonaws.com"
          "${replace(module.eks.oidc_issuer_url, "https://", "")}:sub" = "system:serviceaccount:midas-apps:midas-ec2-mt-test-sa"
        }
      }
    }]
  })

  tags = {
    Environment = var.environment
    ManagedBy   = "terraform"
    Project     = "midas-eks"
  }
}

resource "aws_iam_role_policy_attachment" "ec2_mt_test_s3_results" {
  role       = aws_iam_role.ec2_mt_test.name
  policy_arn = aws_iam_policy.ec2_mt_test_s3_results.arn
}

output "ec2_mt_test_irsa_role_arn" {
  description = "IRSA role ARN for the midas-ec2-mt-test-svc Job pod (S3 results upload)."
  value       = aws_iam_role.ec2_mt_test.arn
}

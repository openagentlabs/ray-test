# MIDAS ECR repository - private registry in the workload account for container images.
# Register in deploy/ecs-app/ecr.tf
#
# EKS worker nodes use the managed policy AmazonEC2ContainerRegistryReadOnly on the
# node role (see modules/eks) to pull images from this account; no extra EKS Terraform
# is required for same-account pulls.

locals {
  repository_name = "midas-${var.environment}-${var.repository_name_suffix}"
  common_tags = {
    Name        = local.repository_name
    Purpose     = "midas-container-images"
    Environment = var.environment
    AccountId   = var.aws_account_id
    ManagedBy   = "Terraform"
  }
}

# Fortify "Insecure ECR Storage": customer-managed KMS key for ECR image
# encryption. One key per module instance (one per ECR repo); simpler than a
# shared key and lets per-repo policies be tightened later.
resource "aws_kms_key" "ecr" {
  description             = "MIDAS ECR encryption — ${local.repository_name}"
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

  tags = local.common_tags
}

resource "aws_kms_alias" "ecr" {
  name          = "alias/${local.repository_name}-ecr"
  target_key_id = aws_kms_key.ecr.key_id
}

resource "aws_ecr_repository" "this" {
  name                 = local.repository_name
  image_tag_mutability = var.image_tag_mutability

  image_scanning_configuration {
    scan_on_push = true
  }

  encryption_configuration {
    encryption_type = "KMS"
    kms_key         = aws_kms_key.ecr.arn
  }

  tags = local.common_tags

  # ECR does not support in-place encryption-type changes; recreating the
  # repository would lose existing image tags. Existing AES256-encrypted
  # repositories stay on AES256 via this ignore_changes; *new* repositories
  # created by this module are KMS-encrypted by default.
  lifecycle {
    ignore_changes = [encryption_configuration]
  }
}

resource "aws_ecr_lifecycle_policy" "this" {
  repository = aws_ecr_repository.this.name

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Keep last N images"
        selection = {
          tagStatus   = "any"
          countType   = "imageCountMoreThan"
          countNumber = var.lifecycle_max_image_count
        }
        action = { type = "expire" }
      }
    ]
  })
}

# Fortify "Improper ECR Access Control" remediation: resource-based policy that
# explicitly allows same-account principals (Jenkins, EKS nodes) and denies any
# cross-account access. IAM identity policies on the node role / Jenkins role
# continue to provide the primary access control; this policy is defense-in-depth.
data "aws_iam_policy_document" "ecr_repo_policy" {
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

resource "aws_ecr_repository_policy" "this" {
  repository = aws_ecr_repository.this.name
  policy     = data.aws_iam_policy_document.ecr_repo_policy.json
}

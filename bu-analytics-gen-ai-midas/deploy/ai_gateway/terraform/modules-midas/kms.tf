resource "aws_kms_key" "eks_cluster_kms_key" {
  deletion_window_in_days  = 7
  enable_key_rotation      = true
  policy                   = data.aws_iam_policy_document.eks_kms.json
  description              = "key for ${var.eks_cluster_name}."
  key_usage                = "ENCRYPT_DECRYPT"
  customer_master_key_spec = "SYMMETRIC_DEFAULT"
  multi_region             = false

  depends_on = [data.aws_iam_policy_document.eks_kms]
}

resource "aws_kms_alias" "eks_cluster_key_alias" {
  name          = "alias/${var.eks_cluster_name}_eks_cluster_kms_key"
  target_key_id = aws_kms_key.eks_cluster_kms_key.key_id
}

resource "aws_kms_key" "efs_kms_key" {

  deletion_window_in_days  = 7
  enable_key_rotation      = true
  policy                   = data.aws_iam_policy_document.efs_kms.json
  description              = "EFS config key for ${var.eks_cluster_name}."
  key_usage                = "ENCRYPT_DECRYPT"
  customer_master_key_spec = "SYMMETRIC_DEFAULT"
  multi_region             = false

  depends_on = [data.aws_iam_policy_document.efs_kms]
}

resource "aws_kms_alias" "efs_kms_alias" {
  name          = "alias/${var.eks_cluster_name}_efs_kms_key"
  target_key_id = aws_kms_key.efs_kms_key.key_id
}

resource "aws_kms_key" "cloudwatch_kms_key" {

  deletion_window_in_days  = 7
  enable_key_rotation      = true
  policy                   = data.aws_iam_policy_document.cloudwatch_kms.json
  description              = "key for ${var.eks_cluster_name} CloudWatch Log Group."
  key_usage                = "ENCRYPT_DECRYPT"
  customer_master_key_spec = "SYMMETRIC_DEFAULT"
  multi_region             = false

  depends_on = [data.aws_iam_policy_document.cloudwatch_kms]
}

resource "aws_kms_alias" "cloudwatch_kms_alias" {
  name          = "alias/${var.eks_cluster_name}_cloudwatch_kms_key"
  target_key_id = aws_kms_key.cloudwatch_kms_key.key_id
}

resource "aws_kms_key" "exlerate_eks_cluster_ecr_kms_key" {

  deletion_window_in_days  = 7
  enable_key_rotation      = true
  policy                   = data.aws_iam_policy_document.ecr_kms.json
  description              = "key for ${var.eks_cluster_name} ECR images."
  key_usage                = "ENCRYPT_DECRYPT"
  customer_master_key_spec = "SYMMETRIC_DEFAULT"
  multi_region             = false

  depends_on = [data.aws_iam_policy_document.ecr_kms]
}

resource "aws_kms_alias" "exlerate_eks_cluster_ecr_kms_alias" {
  name          = "alias/${var.eks_cluster_name}_exlerate_eks_cluster_ecr_kms_key"
  target_key_id = aws_kms_key.exlerate_eks_cluster_ecr_kms_key.key_id
}

# Nodegroup EC2 KMS Key
resource "aws_kms_key" "eks_ec2_ng_kms" {
  deletion_window_in_days  = 7
  enable_key_rotation      = true
  policy                   = data.aws_iam_policy_document.eks_node_group_ec2_kms_policy.json
  description              = "key for ${var.eks_cluster_name} EC2 Volumes."
  key_usage                = "ENCRYPT_DECRYPT"
  customer_master_key_spec = "SYMMETRIC_DEFAULT"
  multi_region             = false

  depends_on = [data.aws_iam_policy_document.eks_node_group_ec2_kms_policy]
}

resource "aws_kms_key" "rds_performance_insights_kms_key" {
  deletion_window_in_days  = 7
  enable_key_rotation      = true
  policy                   = data.aws_iam_policy_document.rds_performance_insights_kms.json
  description              = "KMS key for RDS Performance Insights - ${var.eks_cluster_name}"
  key_usage                = "ENCRYPT_DECRYPT"
  customer_master_key_spec = "SYMMETRIC_DEFAULT"
  multi_region             = false

  depends_on = [data.aws_iam_policy_document.rds_performance_insights_kms]
}

resource "aws_kms_alias" "rds_performance_insights_kms_alias" {
  name          = "alias/${var.eks_cluster_name}_rds_performance_insights_kms_key"
  target_key_id = aws_kms_key.rds_performance_insights_kms_key.key_id
}

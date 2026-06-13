# -----------------------------------------------------------------------------
# EKS access entry for the SSM jump box (ec2-ssm-test) so kubectl works with IAM.
# Requires cluster authentication_mode API_AND_CONFIG_MAP (see modules/eks/main.tf).
# -----------------------------------------------------------------------------

resource "aws_eks_access_entry" "ec2_ssm_jumpbox" {
  cluster_name  = module.eks.eks_cluster_name
  principal_arn = module.ec2_ssm_test.iam_role_arn
  type          = "STANDARD"

  depends_on = [
    module.eks,
    module.ec2_ssm_test,
  ]
}

resource "aws_eks_access_policy_association" "ec2_ssm_jumpbox_cluster_admin" {
  cluster_name  = module.eks.eks_cluster_name
  principal_arn = module.ec2_ssm_test.iam_role_arn
  policy_arn    = "arn:aws:eks::aws:cluster-access-policy/AmazonEKSClusterAdminPolicy"

  access_scope {
    type = "cluster"
  }

  depends_on = [aws_eks_access_entry.ec2_ssm_jumpbox]
}

resource "aws_eks_access_entry" "ec2_ssm_jumpbox_clone" {
  count = var.ec2_ssm_test_clone_enabled ? 1 : 0

  cluster_name  = module.eks.eks_cluster_name
  principal_arn = module.ec2_ssm_test_clone[0].iam_role_arn
  type          = "STANDARD"

  depends_on = [
    module.eks,
    module.ec2_ssm_test_clone,
  ]
}

resource "aws_eks_access_policy_association" "ec2_ssm_jumpbox_clone_cluster_admin" {
  count = var.ec2_ssm_test_clone_enabled ? 1 : 0

  cluster_name  = module.eks.eks_cluster_name
  principal_arn = module.ec2_ssm_test_clone[0].iam_role_arn
  policy_arn    = "arn:aws:eks::aws:cluster-access-policy/AmazonEKSClusterAdminPolicy"

  access_scope {
    type = "cluster"
  }

  depends_on = [aws_eks_access_entry.ec2_ssm_jumpbox_clone]
}

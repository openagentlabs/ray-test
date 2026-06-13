# -----------------------------------------------------------------------------
# Optional EKS access entry for CI/automation (e.g. Jenkins using midas-deployer-role)
# so helm/kubectl can run against the private API when network path exists.
# Set var.eks_ci_automation_principal_arn to the role ARN (e.g. arn:aws:iam::ACCOUNT:role/midas-deployer-role).
# -----------------------------------------------------------------------------

resource "aws_eks_access_entry" "ci_automation" {
  count = var.eks_ci_automation_principal_arn != "" ? 1 : 0

  cluster_name  = module.eks.eks_cluster_name
  principal_arn = var.eks_ci_automation_principal_arn
  type          = "STANDARD"

  depends_on = [
    module.eks,
  ]
}

resource "aws_eks_access_policy_association" "ci_automation_cluster_admin" {
  count = var.eks_ci_automation_principal_arn != "" ? 1 : 0

  cluster_name  = module.eks.eks_cluster_name
  principal_arn = var.eks_ci_automation_principal_arn
  policy_arn    = "arn:aws:eks::aws:cluster-access-policy/AmazonEKSClusterAdminPolicy"

  access_scope {
    type = "cluster"
  }

  depends_on = [aws_eks_access_entry.ci_automation]
}

# -----------------------------------------------------------------------------
# Allow the SSM jump box (ec2-ssm-test) to reach the private EKS Kubernetes API
# on TCP 443. Jenkins CIDR remains on cluster SG via modules/eks (cidr rule);
# this adds a least-privilege SG-to-SG path for midas-*-ec2-ssm-test-sg.
# -----------------------------------------------------------------------------

resource "aws_security_group_rule" "eks_cluster_api_https_from_ec2_ssm_jumpbox" {
  description              = "Kubernetes API (443) from SSM jump box (ec2-ssm-test)"
  type                     = "ingress"
  from_port                = 443
  to_port                  = 443
  protocol                 = "tcp"
  security_group_id        = module.eks.eks_cluster_security_group_id
  source_security_group_id = module.ec2_ssm_test.security_group_id

  depends_on = [
    module.eks,
    module.ec2_ssm_test,
  ]
}

resource "aws_security_group_rule" "eks_node_http8080_from_ec2_ssm_jumpbox" {
  description              = "Pod HTTP (8080) from SSM jump box for port-forward tunnelling"
  type                     = "ingress"
  from_port                = 8080
  to_port                  = 8080
  protocol                 = "tcp"
  security_group_id        = module.eks.eks_cluster_security_group_id
  source_security_group_id = module.ec2_ssm_test.security_group_id

  depends_on = [
    module.eks,
    module.ec2_ssm_test,
  ]
}

resource "aws_security_group_rule" "eks_cluster_api_https_from_ec2_ssm_jumpbox_clone" {
  count = var.ec2_ssm_test_clone_enabled ? 1 : 0

  description              = "Kubernetes API (443) from SSM jump box clone (ec2-ssm-test-clone)"
  type                     = "ingress"
  from_port                = 443
  to_port                  = 443
  protocol                 = "tcp"
  security_group_id        = module.eks.eks_cluster_security_group_id
  source_security_group_id = module.ec2_ssm_test_clone[0].security_group_id

  depends_on = [
    module.eks,
    module.ec2_ssm_test_clone,
  ]
}

resource "aws_security_group_rule" "eks_node_http8080_from_ec2_ssm_jumpbox_clone" {
  count = var.ec2_ssm_test_clone_enabled ? 1 : 0

  description              = "Pod HTTP (8080) from SSM jump box clone for port-forward tunnelling"
  type                     = "ingress"
  from_port                = 8080
  to_port                  = 8080
  protocol                 = "tcp"
  security_group_id        = module.eks.eks_cluster_security_group_id
  source_security_group_id = module.ec2_ssm_test_clone[0].security_group_id

  depends_on = [
    module.eks,
    module.ec2_ssm_test_clone,
  ]
}

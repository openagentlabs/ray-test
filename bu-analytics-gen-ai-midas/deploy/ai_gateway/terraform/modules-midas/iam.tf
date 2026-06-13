resource "aws_iam_role" "eks_cluster_role" {
  name                  = "exl-${var.eks_cluster_name}-role"
  path                  = "/"
  max_session_duration  = 3600
  description           = "This IAM Role is used for EKS Cluster"
  force_detach_policies = true
  assume_role_policy    = data.aws_iam_policy_document.eks_cluster_role_trusted_policy.json
}

# Attach AWS managed policies
resource "aws_iam_role_policy_attachment" "eks_managed_policy_attach" {
  for_each   = { for arn in local.eks_cluster_managed_policy_arns : arn => arn }
  role       = aws_iam_role.eks_cluster_role.name
  policy_arn = each.key
}

# AWS EKS NG Role #
resource "aws_iam_role" "eks_node_group_role" {
  name                  = "exl-${var.eks_cluster_name}-ng-role"
  path                  = "/"
  max_session_duration  = 3600
  description           = "This IAM Role is used for EKS Cluster Node Group"
  force_detach_policies = true
  assume_role_policy    = data.aws_iam_policy_document.eks_node_role_trusted_policy.json
}

resource "aws_iam_role_policy_attachment" "eks_ng_managed_attached_policy" {
  for_each   = { for arn in local.node_group_policy_arns : arn => arn }
  role       = aws_iam_role.eks_node_group_role.name
  policy_arn = each.key
}

# NG Role policy
resource "aws_iam_policy" "ng_role_policy" {
  name        = "exl-${var.eks_cluster_name}-ng-inline-policy"
  path        = "/"
  description = "SSM execution policy"
  policy      = data.aws_iam_policy_document.eks_nodegroup_policy.json
}

resource "aws_iam_role_policy_attachment" "ng_policy_attach" {
  role       = aws_iam_role.eks_node_group_role.name
  policy_arn = aws_iam_policy.ng_role_policy.arn
}


# EBS IAM Role policy
resource "aws_iam_role" "eks_ebs_addon_role" {
  name                  = "exl-${var.eks_cluster_name}-ebs-addon-role"
  path                  = "/"
  max_session_duration  = 3600
  description           = "This IAM Role is used for EKS EBS Add on role"
  force_detach_policies = true
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Federated = "arn:aws:iam::${local.account_id}:oidc-provider/${local.eks_oidc_url}"
        }
        Action = "sts:AssumeRoleWithWebIdentity",
        Condition = {
          StringEquals = {
            "${local.eks_oidc_url}:sub" : "system:serviceaccount:kube-system:ebs-csi-controller-sa",
            "${local.eks_oidc_url}:aud" : "sts.amazonaws.com"
          }
        }
      }
    ]
  })
}

resource "aws_iam_policy" "ebs_addon_policy" {
  name        = "${var.eks_cluster_name}-ebs-addon-inline-policy"
  path        = "/"
  description = "Additional permissions needed by EBS add on"
  policy      = data.aws_iam_policy_document.eks_ebs_add_on_policy.json
}

resource "aws_iam_role_policy_attachment" "eks_ebs_addon_policy" {
  role       = aws_iam_role.eks_ebs_addon_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonEBSCSIDriverPolicy"
}

resource "aws_iam_role_policy_attachment" "eks_ebs_addon_policy_2" {
  role       = aws_iam_role.eks_ebs_addon_role.name
  policy_arn = aws_iam_policy.ebs_addon_policy.arn
}

# Linkage between EKS ServiceAccount and predefined IAM role
resource "kubernetes_service_account_v1" "ebs_addon_irsa_sa" {
  metadata {
    name      = "ebs-csi-controller-sa-${var.environment}"
    namespace = "kube-system"

    annotations = {
      "eks.amazonaws.com/role-arn" = aws_iam_role.eks_ebs_addon_role.arn
    }
  }
}

## S3 Config bucket policy.
resource "aws_iam_policy" "litellm_s3_config_policy" {
  name        = "${var.eks_cluster_name}-litellm-s3-config-policy"
  path        = "/"
  description = "Additional permissions for reading S3 bucket config"
  policy      = data.aws_iam_policy_document.litellm_s3_config_policy.json
}

## S3 Config bucket policy Langfuse.
resource "aws_iam_policy" "langfuse_s3_config_policy" {
  name        = "${var.eks_cluster_name}-langfuse-s3-config-policy"
  path        = "/"
  description = "Additional permissions for reading S3 bucket config"
  policy      = data.aws_iam_policy_document.langfuse_s3_config_policy.json
}


# Karpenter IAM policy for IRSA definition 
# Ignore for now, this will be picked up later for use off Karpenter in later environments
# resource "aws_iam_policy" "karpenter_controller" {
#   name        = "KarpenterControllerPolicy-${var.environment}"
#   description = "Karpenter application policy for scaling managed controllers"
#   policy      = data.aws_iam_policy_document.karpenter_iam_policy.json
# }
# resource "aws_iam_role" "karpenter_iam_role" {
#   name                  = "karpenter-role-${var.environment}"
#   path                  = "/"
#   max_session_duration  = 3600
#   description           = "This IAM Role is used for karpenter application running EKS Cluster"
#   force_detach_policies = true
#   assume_role_policy = jsonencode({
#     Version = "2012-10-17"
#     Statement = [{
#       Effect = "Allow"
#       Action = "sts:AssumeRoleWithWebIdentity"
#       Principal = {
#         Federated = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:oidc-provider/${local.eks_oidc_url}"
#       }
#       Condition = {
#         StringEquals = {
#           "${local.eks_oidc_url}:sub" = "system:serviceaccount:karpenter:karpenter" #IRSA and namespace
#         }
#       }
#     }]
#   })
# }

# resource "aws_iam_role_policy_attachment" "karpenter_pol_att" {
#   role       = aws_iam_role.karpenter_iam_role.name
#   policy_arn = aws_iam_policy.karpenter_controller.arn
# }

# # Karpenter Node role
# resource "aws_iam_role" "karpenter_node_role" {
#   name = "KarpenterNodeRole"

#   assume_role_policy = jsonencode({
#     Version = "2012-10-17"
#     Statement = [{
#       Effect    = "Allow"
#       Principal = { Service = "ec2.amazonaws.com" }
#       Action    = "sts:AssumeRole"
#     }]
#   })
# }

# resource "aws_iam_role_policy_attachment" "node" {
#   for_each   = toset(local.karpenter_node_policies)
#   role       = aws_iam_role.karpenter_node_role.name
#   policy_arn = each.value
# }

# ALB Policy 
resource "aws_iam_policy" "alb_controller_policy" {
  name        = "${var.eks_cluster_name}-alb-policy"
  description = "Needed for new EKS ALB definitions"
  policy      = data.aws_iam_policy_document.alb_controller.json
}


#############################
#     RDS IAM Role 
#############################
resource "aws_iam_role" "rds_enhanced_monitoring" {
  name = "${var.eks_cluster_name}-rds-enhanced-monitoring-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Service = "monitoring.rds.amazonaws.com"
      }
      Action = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "rds_monitoring_attach" {
  role       = aws_iam_role.rds_enhanced_monitoring.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonRDSEnhancedMonitoringRole"
}
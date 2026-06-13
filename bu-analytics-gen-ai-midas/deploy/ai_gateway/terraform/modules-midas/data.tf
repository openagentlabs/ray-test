data "aws_caller_identity" "current" {}

data "aws_region" "current" {}

data "aws_subnet" "selected_azs" {
  for_each = toset(var.subnet_ids)
  id       = each.value
}

## EKS Cluster role
data "aws_iam_policy_document" "eks_cluster_role_trusted_policy" {
  statement {
    actions = ["sts:AssumeRole"]
    effect  = "Allow"
    principals {
      type        = "Service"
      identifiers = ["eks.amazonaws.com"]
    }
  }
}

# EKS Node group
data "aws_iam_policy_document" "eks_nodegroup_policy" {
  #checkov:skip=CKV_AWS_356:Non-restrictable wildcard action patterns (e.g. route53:Get*, logs:Get*) cannot be decomposed without enumerating every individual API; restrictable actions are already scoped to service-specific ARN patterns in dedicated statements below
  # Non-restrictable read actions — AWS does not support resource-level scoping for Describe/List
  statement {
    sid    = "NonRestrictableReadActions"
    effect = "Allow"
    actions = [
      "ec2:Describe*",
      "rds:Describe*",
      "elasticloadbalancing:Describe*",
      "elasticache:Describe*",
      "elasticfilesystem:Describe*",
      "route53:List*",
      "route53:Get*",
      "route53resolver:List*",
      "route53resolver:Get*",
      "cloudtrail:LookupEvents",
      "logs:Describe*",
      "logs:Get*",
      "logs:List*",
      "ecr:GetAuthorizationToken",
      "iam:ListRoles",
    ]
    resources = ["*"]
  }

  # S3 bucket access
  statement {
    sid    = "S3Access"
    effect = "Allow"
    actions = [
      "s3:GetObject",
      "s3:PutObject",
      "s3:ListBucket",
    ]
    resources = ["arn:aws:s3:::*", "arn:aws:s3:::*/*"]
  }

  # KMS key operations
  statement {
    sid    = "KMSAccess"
    effect = "Allow"
    actions = [
      "kms:CreateGrant",
      "kms:Encrypt",
      "kms:Decrypt",
      "kms:DescribeKey",
      "kms:GenerateDataKey",
      "kms:GenerateDataKeyWithoutPlainText",
      "kms:ReEncrypt*",
    ]
    resources = ["arn:aws:kms:*:*:key/*"]
  }

  # IAM role operations
  statement {
    sid    = "IAMRoleAccess"
    effect = "Allow"
    actions = [
      "iam:GetRole",
      "iam:PassRole",
    ]
    resources = ["arn:aws:iam::*:role/*"]
  }

  # ECR image pull
  statement {
    sid    = "ECRImagePull"
    effect = "Allow"
    actions = [
      "ecr:BatchGetImage",
      "ecr:GetDownloadUrlForLayer",
      "ecr:BatchCheckLayerAvailability",
    ]
    resources = ["arn:aws:ecr:*:*:repository/*"]
  }

  # EKS cluster access (DescribeCluster + pod-identity assumption)
  statement {
    sid    = "EKSClusterAccess"
    effect = "Allow"
    actions = [
      "eks:DescribeCluster",
      "eks:ListClusters",
      "eks-auth:AssumeRoleForPodIdentity",
    ]
    resources = ["arn:aws:eks:*:*:cluster/*"]
  }

  # SSM agent message relay (scoped to EC2 instances)
  statement {
    sid    = "SSMAgentMessageRelay"
    effect = "Allow"
    actions = [
      "ec2messages:AcknowledgeMessage",
      "ec2messages:DeleteMessage",
      "ec2messages:FailMessage",
      "ec2messages:GetEndpoint",
      "ec2messages:GetMessages",
      "ec2messages:SendReply",
    ]
    resources = ["arn:aws:ec2:*:*:instance/*"]
  }
}

data "aws_iam_policy_document" "eks_node_role_trusted_policy" {
  statement {
    actions = ["sts:AssumeRole"]
    effect  = "Allow"
    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

## Node group KMS Volume policy
data "aws_iam_policy_document" "eks_node_group_ec2_kms_policy" {
  #checkov:skip=CKV_AWS_356:KMS key resource policy — AWS requires resources="*" to mean "this KMS key"; any other value is invalid per AWS KMS key-policy specification
  # Node group IAM role access
  statement {
    effect = "Allow"
    actions = [
      "kms:Encrypt",
      "kms:Decrypt",
      "kms:ReEncrypt*",
      "kms:GenerateDataKey*",
      "kms:DescribeKey",
      "kms:CreateGrant",
      "kms:ListGrants",
      "kms:RevokeGrant"
    ]
    principals {
      type        = "Service"
      identifiers = ["eks.amazonaws.com", "ec2.amazonaws.com", "autoscaling.amazonaws.com"]
    }
    resources = ["*"]
  }
  statement {
    effect = "Allow"
    actions = [
      "kms:*",
    ]
    principals {
      type        = "AWS"
      identifiers = ["arn:aws:iam::${local.account_id}:root"]
    }
    resources = ["*"]
  }
  statement {
    effect = "Allow"
    actions = [
      "kms:Create*",
      "kms:Describe*",
      "kms:Enable*",
      "kms:List*",
      "kms:Put*",
      "kms:Update*",
      "kms:Revoke*",
      "kms:Disable*",
      "kms:Get*",
      "kms:Delete*",
      "kms:TagResource",
      "kms:UntagResource",
      "kms:ScheduleKeyDeletion",
      "kms:CancelKeyDeletion",
      "kms:RotateKeyOnDemand",
      "kms:Encrypt",
      "kms:Decrypt",
      "kms:ReEncrypt*",
      "kms:GenerateDataKey*",
      "kms:CreateGrant"
    ]
    principals {
      type        = "AWS"
      identifiers = [var.architect_role_arn, aws_iam_role.eks_node_group_role.arn]
    }
    resources = ["*"]
  }

  statement {
    sid    = "KMS Access for EKS, EC2 Autoscaling service"
    effect = "Allow"
    actions = [
      "kms:Encrypt",
      "kms:Decrypt",
      "kms:ReEncrypt*",
      "kms:GenerateDataKey*",
      "kms:DescribeKey",
      "kms:ListGrants",
      "kms:RevokeGrant",
      "kms:CreateGrant"
    ]
    resources = ["*"]
    principals {
      type = "AWS"
      identifiers = [
        "arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/aws-service-role/autoscaling.amazonaws.com/AWSServiceRoleForAutoScaling",
      aws_iam_role.eks_node_group_role.arn]

    }
  }
}


data "aws_iam_policy_document" "eks_kms" {
  #checkov:skip=CKV_AWS_356:KMS key resource policy — AWS requires resources="*" to mean "this KMS key"; any other value is invalid per AWS KMS key-policy specification
  statement {
    sid       = "AllowAccountRoot"
    actions   = ["kms:*"]
    effect    = "Allow"
    resources = ["*"]
    principals {
      type        = "AWS"
      identifiers = ["arn:aws:iam::${local.account_id}:root"]
    }
  }
}

data "aws_iam_policy_document" "efs_kms" {
  #checkov:skip=CKV_AWS_356:KMS key resource policy — AWS requires resources="*" to mean "this KMS key"; any other value is invalid per AWS KMS key-policy specification
  statement {
    actions   = ["kms:*", ]
    effect    = "Allow"
    resources = ["*"]
    principals {
      type        = "AWS"
      identifiers = ["arn:aws:iam::${local.account_id}:root"]
    }
    principals {
      type = "Service"
      identifiers = [
        "eks.amazonaws.com",
      "elasticfilesystem.amazonaws.com"]
    }
  }
}

data "aws_iam_policy_document" "cloudwatch_kms" {
  #checkov:skip=CKV_AWS_356:KMS key resource policy — AWS requires resources="*" to mean "this KMS key"; any other value is invalid per AWS KMS key-policy specification
  statement {
    actions = [
      "kms:Encrypt",
      "kms:Decrypt",
      "kms:ReEncrypt*",
      "kms:GenerateDataKey*",
      "kms:Describe*",
      "kms:Get*",
      "kms:List*",
      "kms:CreateGrant",
      "kms:ListGrants",
    "kms:RevokeGrant"]
    effect    = "Allow"
    resources = ["*"]
    principals {
      type        = "Service"
      identifiers = ["logs.${local.aws_region}.amazonaws.com"]
    }

    condition {
      test     = "ArnEquals"
      variable = "kms:EncryptionContext:aws:logs:arn"
      values   = ["arn:aws:logs:${local.aws_region}:${local.account_id}:log-group:${var.log_group_name}*"]
    }
  }

  statement {
    actions = ["kms:*"]
    effect  = "Allow"
    principals {
      type        = "AWS"
      identifiers = ["arn:aws:iam::${local.account_id}:root"]
    }
    resources = ["*"]
  }
}

data "aws_iam_policy_document" "ecr_kms" {
  #checkov:skip=CKV_AWS_356:KMS key resource policy — AWS requires resources="*" to mean "this KMS key"; any other value is invalid per AWS KMS key-policy specification
  statement {
    actions   = ["kms:*"]
    effect    = "Allow"
    resources = ["*"]

    principals {
      type        = "AWS"
      identifiers = ["arn:aws:iam::${local.account_id}:root"]
    }
  }
}

# Needed for PVC persistence.
data "aws_iam_policy_document" "eks_ebs_add_on_policy" {
  # Non-restrictable describe actions — AWS does not support resource-level scoping for ec2:Describe*
  statement {
    sid    = "EBSDescribeActions"
    effect = "Allow"
    actions = [
      "ec2:DescribeAvailabilityZones",
      "ec2:DescribeInstances",
      "ec2:DescribeSnapshots",
      "ec2:DescribeTags",
      "ec2:DescribeVolumes",
      "ec2:DescribeVolumeStatus",
    ]
    resources = ["*"]
  }

  # EBS volume lifecycle actions scoped to volume/instance/snapshot ARNs
  statement {
    sid    = "EBSVolumeManagement"
    effect = "Allow"
    actions = [
      "ec2:CreateVolume",
      "ec2:AttachVolume",
      "ec2:DetachVolume",
      "ec2:DeleteVolume",
      "ec2:ModifyVolume",
      "ec2:CreateTags",
      "ec2:ListTagsForResource",
    ]
    resources = [
      "arn:aws:ec2:*:*:volume/*",
      "arn:aws:ec2:*:*:instance/*",
      "arn:aws:ec2:*:*:snapshot/*",
    ]
  }

  # KMS operations for EBS encryption scoped to specific KMS keys
  statement {
    sid    = "EBSKMSAccess"
    effect = "Allow"
    actions = [
      "kms:CreateGrant",
      "kms:DescribeKey",
      "kms:Encrypt",
      "kms:Decrypt",
      "kms:GenerateDataKey*",
      "kms:ListGrants",
    ]
    resources = ["arn:aws:kms:*:*:key/*"]
  }
}

# LiteLLM S3 Custom Access Role
data "aws_iam_policy_document" "litellm_s3_config_policy" {
  #checkov:skip=CKV_AWS_356:Non-restrictable wildcard action patterns for Bedrock List*/Get* and aws-marketplace cannot be decomposed to specific ARNs; model invocation, resource management, and SageMaker actions are scoped to service-specific ARN patterns in dedicated statements below
  statement {
    actions = [
      "s3:GetObject",
      "s3:PutObject",
      "s3:ListBucket",
      "s3:PutObjectAcl",
      "s3:PutObject",
      "s3:ListBucket",
      "s3:GetBucketLocation",
      "s3:AbortMultipartUpload"
    ]
    effect    = "Allow"
    resources = ["${aws_s3_bucket.exlerate_config_bucket.arn}/*"]
  }
  statement {
    actions = [
      "s3:PutObjectAcl",
      "s3:PutObject",
      "s3:ListBucket",
      "s3:GetBucketLocation",
      "s3:AbortMultipartUpload"
    ]
    effect = "Allow"
    resources = [
      "${aws_s3_bucket.exlerate_log_bucket.arn}/*",
      aws_s3_bucket.exlerate_log_bucket.arn
    ]
    sid = "S3LogBucketAccess"
  }
  # Non-restrictable read actions and marketplace — AWS does not support resource-level scoping for these
  statement {
    sid    = "BedrockAccessNonRestrictable"
    effect = "Allow"
    actions = [
      "iam:ListRoles",
      "ec2:DescribeVpcs",
      "ec2:DescribeSubnets",
      "ec2:DescribeSecurityGroups",
      "bedrock:List*",
      "bedrock:Get*",
      "aws-marketplace:ViewSubscriptions",
      "aws-marketplace:Unsubscribe",
      "aws-marketplace:Subscribe",
    ]
    resources = ["*"]
  }

  # Bedrock foundation model and inference-profile invocation
  statement {
    sid    = "BedrockModelInvoke"
    effect = "Allow"
    actions = [
      "bedrock:InvokeModel",
      "bedrock:InvokeModelWithResponseStream",
      "bedrock:ApplyGuardrail",
      "bedrock:CallWithBearerToken",
    ]
    resources = [
      "arn:aws:bedrock:*::foundation-model/*",
      "arn:aws:bedrock:*:*:inference-profile/*",
      "arn:aws:bedrock:*:*:provisioned-model/*",
      "arn:aws:bedrock:*:*:guardrail/*",
    ]
  }

  # Bedrock resource management (guardrails, provisioned throughput, evaluation jobs, etc.)
  statement {
    sid    = "BedrockResourceManagement"
    effect = "Allow"
    actions = [
      "bedrock:UpdateProvisionedModelThroughput",
      "bedrock:UpdateGuardrail",
      "bedrock:UntagResource",
      "bedrock:TagResource",
      "bedrock:StopModelInvocationJob",
      "bedrock:StopModelCustomizationJob",
      "bedrock:StopEvaluationJob",
      "bedrock:DeleteProvisionedModelThroughput",
      "bedrock:DeletePromptRouter",
      "bedrock:DeleteInferenceProfile",
      "bedrock:DeleteImportedModel",
      "bedrock:DeleteGuardrail",
      "bedrock:DeleteCustomModel",
      "bedrock:CreateProvisionedModelThroughput",
      "bedrock:CreatePromptRouter",
      "bedrock:CreateModelInvocationJob",
      "bedrock:CreateModelImportJob",
      "bedrock:CreateModelCustomizationJob",
      "bedrock:CreateModelCopyJob",
      "bedrock:CreateInferenceProfile",
      "bedrock:CreateGuardrailVersion",
      "bedrock:CreateGuardrail",
      "bedrock:CreateEvaluationJob",
      "bedrock:BatchDeleteEvaluationJob",
    ]
    resources = ["arn:aws:bedrock:*:*:*"]
  }

  # SageMaker endpoint invocation scoped to endpoint ARNs
  statement {
    sid       = "SageMakerInvoke"
    effect    = "Allow"
    actions   = ["sagemaker:InvokeEndpoint"]
    resources = ["arn:aws:sagemaker:*:*:endpoint/*"]
  }
}

data "aws_iam_policy_document" "langfuse_s3_config_policy" {
  statement {
    actions = [
      "s3:GetObject",
      "s3:PutObject",
      "s3:DeleteObject",
      "s3:ListBucket"
    ]
    effect = "Allow"
    resources = [
      aws_s3_bucket.exlerate_langfuse_data_bucket.arn,
      "${aws_s3_bucket.exlerate_langfuse_data_bucket.arn}/*",
      aws_s3_bucket.exlerate_langfuse_media_bucket.arn,
      "${aws_s3_bucket.exlerate_langfuse_media_bucket.arn}/*",
    ]
  }
}

data "aws_iam_policy_document" "karpenter_iam_policy" {
  #checkov:skip=CKV_AWS_356:Standard Karpenter node-provisioner policy — actions such as ec2:RunInstances, ec2:CreateFleet, and ec2:CreateLaunchTemplate require resources="*" because Karpenter creates resources dynamically and their ARNs are not known at policy-evaluation time
  #checkov:skip=CKV_AWS_110:iam:PassRole is the minimum documented Karpenter IAM requirement — Karpenter must pass an instance profile role to EC2 nodes it provisions (see https://karpenter.sh/docs/reference/iam/). Removing PassRole breaks node bootstrap.
  statement {
    actions = [
      "ec2:CreateLaunchTemplate",
      "ec2:CreateFleet",
      "ec2:RunInstances",
      "ec2:CreateTags",
      "ec2:TerminateInstances",
      "ec2:DeleteLaunchTemplate",
      "ec2:Describe*",
      "iam:PassRole",
      "iam:GetInstanceProfile",
      "iam:CreateInstanceProfile",
      "iam:ListInstanceProfiles",
      "iam:TagInstanceProfile",
      "iam:AddRoleToInstanceProfile",
      "iam:RemoveRoleFromInstanceProfile",
      "iam:DeleteInstanceProfile",
      "pricing:GetProducts",
      "ssm:GetParameter"
    ]
    effect    = "Allow"
    resources = ["*"]
  }
}

##############################
### LB Policy permissions ####
##############################
data "aws_iam_policy_document" "alb_controller" {
  #checkov:skip=CKV_AWS_356:AWS-published ALB Ingress Controller policy — actions such as ec2:CreateSecurityGroup, elasticloadbalancing:CreateListener, and elasticloadbalancing:CreateRule require resources="*" because the target resource does not exist at policy-evaluation time

  statement {
    effect = "Allow"

    actions = [
      "iam:CreateServiceLinkedRole"
    ]

    resources = ["*"]

    condition {
      test     = "StringEquals"
      variable = "iam:AWSServiceName"
      values   = ["elasticloadbalancing.amazonaws.com"]
    }
  }

  statement {
    effect = "Allow"

    actions = [
      "ec2:DescribeAccountAttributes",
      "ec2:DescribeAddresses",
      "ec2:DescribeAvailabilityZones",
      "ec2:DescribeInternetGateways",
      "ec2:DescribeVpcs",
      "ec2:DescribeVpcPeeringConnections",
      "ec2:DescribeSubnets",
      "ec2:DescribeSecurityGroups",
      "ec2:DescribeInstances",
      "ec2:DescribeNetworkInterfaces",
      "ec2:DescribeTags",
      "ec2:GetCoipPoolUsage",
      "ec2:DescribeCoipPools",
      "ec2:GetSecurityGroupsForVpc",
      "ec2:DescribeIpamPools",
      "ec2:DescribeRouteTables",
      "elasticloadbalancing:DescribeLoadBalancers",
      "elasticloadbalancing:DescribeLoadBalancerAttributes",
      "elasticloadbalancing:DescribeListeners",
      "elasticloadbalancing:DescribeListenerCertificates",
      "elasticloadbalancing:DescribeSSLPolicies",
      "elasticloadbalancing:DescribeRules",
      "elasticloadbalancing:DescribeTargetGroups",
      "elasticloadbalancing:DescribeTargetGroupAttributes",
      "elasticloadbalancing:DescribeTargetHealth",
      "elasticloadbalancing:DescribeTags",
      "elasticloadbalancing:DescribeTrustStores",
      "elasticloadbalancing:DescribeListenerAttributes",
      "elasticloadbalancing:DescribeCapacityReservation"
    ]

    resources = ["*"]
  }

  statement {
    effect = "Allow"

    actions = [
      "cognito-idp:DescribeUserPoolClient",
      "acm:ListCertificates",
      "acm:DescribeCertificate",
      "iam:ListServerCertificates",
      "iam:GetServerCertificate",
      "waf-regional:GetWebACL",
      "waf-regional:GetWebACLForResource",
      "waf-regional:AssociateWebACL",
      "waf-regional:DisassociateWebACL",
      "wafv2:GetWebACL",
      "wafv2:GetWebACLForResource",
      "wafv2:AssociateWebACL",
      "wafv2:DisassociateWebACL",
      "shield:GetSubscriptionState",
      "shield:DescribeProtection",
      "shield:CreateProtection",
      "shield:DeleteProtection"
    ]

    resources = ["*"]
  }

  statement {
    effect = "Allow"

    actions = [
      "ec2:AuthorizeSecurityGroupIngress",
      "ec2:RevokeSecurityGroupIngress"
    ]

    resources = ["*"]
  }

  statement {
    effect = "Allow"

    actions = [
      "ec2:CreateSecurityGroup"
    ]

    resources = ["*"]
  }

  statement {
    effect = "Allow"

    actions = [
      "ec2:CreateTags"
    ]

    resources = ["arn:aws:ec2:*:*:security-group/*"]

    condition {
      test     = "StringEquals"
      variable = "ec2:CreateAction"
      values   = ["CreateSecurityGroup"]
    }

    condition {
      test     = "Null"
      variable = "aws:RequestTag/elbv2.k8s.aws/cluster"
      values   = ["false"]
    }
  }

  statement {
    effect = "Allow"

    actions = [
      "ec2:CreateTags",
      "ec2:DeleteTags"
    ]

    resources = ["arn:aws:ec2:*:*:security-group/*"]

    condition {
      test     = "Null"
      variable = "aws:RequestTag/elbv2.k8s.aws/cluster"
      values   = ["true"]
    }

    condition {
      test     = "Null"
      variable = "aws:ResourceTag/elbv2.k8s.aws/cluster"
      values   = ["false"]
    }
  }

  statement {
    effect = "Allow"

    actions = [
      "ec2:AuthorizeSecurityGroupIngress",
      "ec2:RevokeSecurityGroupIngress",
      "ec2:DeleteSecurityGroup"
    ]

    resources = ["*"]

    condition {
      test     = "Null"
      variable = "aws:ResourceTag/elbv2.k8s.aws/cluster"
      values   = ["false"]
    }
  }

  statement {
    effect = "Allow"

    actions = [
      "elasticloadbalancing:CreateLoadBalancer",
      "elasticloadbalancing:CreateTargetGroup"
    ]

    resources = ["*"]

    condition {
      test     = "Null"
      variable = "aws:RequestTag/elbv2.k8s.aws/cluster"
      values   = ["false"]
    }
  }

  statement {
    effect = "Allow"

    actions = [
      "elasticloadbalancing:CreateListener",
      "elasticloadbalancing:DeleteListener",
      "elasticloadbalancing:CreateRule",
      "elasticloadbalancing:DeleteRule"
    ]

    resources = ["*"]
  }

  statement {
    effect = "Allow"

    actions = [
      "elasticloadbalancing:AddTags",
      "elasticloadbalancing:RemoveTags"
    ]

    resources = [
      "arn:aws:elasticloadbalancing:*:*:targetgroup/*/*",
      "arn:aws:elasticloadbalancing:*:*:loadbalancer/net/*/*",
      "arn:aws:elasticloadbalancing:*:*:loadbalancer/app/*/*"
    ]

    condition {
      test     = "Null"
      variable = "aws:RequestTag/elbv2.k8s.aws/cluster"
      values   = ["true"]
    }

    condition {
      test     = "Null"
      variable = "aws:ResourceTag/elbv2.k8s.aws/cluster"
      values   = ["false"]
    }
  }

  statement {
    effect = "Allow"

    actions = [
      "elasticloadbalancing:AddTags",
      "elasticloadbalancing:RemoveTags"
    ]

    resources = [
      "arn:aws:elasticloadbalancing:*:*:listener/net/*/*/*",
      "arn:aws:elasticloadbalancing:*:*:listener/app/*/*/*",
      "arn:aws:elasticloadbalancing:*:*:listener-rule/net/*/*/*",
      "arn:aws:elasticloadbalancing:*:*:listener-rule/app/*/*/*"
    ]
  }

  statement {
    effect = "Allow"

    actions = [
      "elasticloadbalancing:ModifyLoadBalancerAttributes",
      "elasticloadbalancing:SetIpAddressType",
      "elasticloadbalancing:SetSecurityGroups",
      "elasticloadbalancing:SetSubnets",
      "elasticloadbalancing:DeleteLoadBalancer",
      "elasticloadbalancing:ModifyTargetGroup",
      "elasticloadbalancing:ModifyTargetGroupAttributes",
      "elasticloadbalancing:DeleteTargetGroup",
      "elasticloadbalancing:ModifyListenerAttributes",
      "elasticloadbalancing:ModifyCapacityReservation",
      "elasticloadbalancing:ModifyIpPools"
    ]

    resources = ["*"]

    condition {
      test     = "Null"
      variable = "aws:ResourceTag/elbv2.k8s.aws/cluster"
      values   = ["false"]
    }
  }

  statement {
    effect = "Allow"

    actions = [
      "elasticloadbalancing:AddTags"
    ]

    resources = [
      "arn:aws:elasticloadbalancing:*:*:targetgroup/*/*",
      "arn:aws:elasticloadbalancing:*:*:loadbalancer/net/*/*",
      "arn:aws:elasticloadbalancing:*:*:loadbalancer/app/*/*"
    ]

    condition {
      test     = "StringEquals"
      variable = "elasticloadbalancing:CreateAction"
      values = [
        "CreateTargetGroup",
        "CreateLoadBalancer"
      ]
    }

    condition {
      test     = "Null"
      variable = "aws:RequestTag/elbv2.k8s.aws/cluster"
      values   = ["false"]
    }
  }

  statement {
    effect = "Allow"

    actions = [
      "elasticloadbalancing:RegisterTargets",
      "elasticloadbalancing:DeregisterTargets"
    ]

    resources = [
      "arn:aws:elasticloadbalancing:*:*:targetgroup/*/*"
    ]
  }

  statement {
    effect = "Allow"

    actions = [
      "elasticloadbalancing:SetWebAcl",
      "elasticloadbalancing:ModifyListener",
      "elasticloadbalancing:AddListenerCertificates",
      "elasticloadbalancing:RemoveListenerCertificates",
      "elasticloadbalancing:ModifyRule",
      "elasticloadbalancing:SetRulePriorities"
    ]

    resources = ["*"]
  }
}

data "aws_iam_policy_document" "rds_performance_insights_kms" {
  #checkov:skip=CKV_AWS_356:KMS key resource policy — AWS requires resources="*" to mean "this KMS key"; any other value is invalid per AWS KMS key-policy specification
  statement {
    sid    = "AllowRDSPerformanceInsights"
    effect = "Allow"
    actions = [
      "kms:Decrypt",
      "kms:GenerateDataKey",
      "kms:CreateGrant",
      "kms:DescribeKey",
    ]
    principals {
      type        = "Service"
      identifiers = ["rds.amazonaws.com"]
    }
    resources = ["*"]
  }
  statement {
    sid     = "AllowAccountRoot"
    effect  = "Allow"
    actions = ["kms:*"]
    principals {
      type        = "AWS"
      identifiers = ["arn:aws:iam::${local.account_id}:root"]
    }
    resources = ["*"]
  }
}
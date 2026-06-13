# Private Ubuntu test instance with SSM Session Manager (no SSH ingress).
# Subnet: prefers exl:uc:SubnetGroup=1 (larger tiers per MIDAS VPC layout), then 2, then any subnet in the VPC.

locals {
  name_prefix = "midas-${var.environment}-ec2-ssm-test${var.resource_name_suffix}"
}

data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"]

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }

  filter {
    name   = "architecture"
    values = ["x86_64"]
  }
}

data "aws_subnets" "tier1" {
  filter {
    name   = "vpc-id"
    values = [var.vpc_id]
  }
  filter {
    name   = "tag:exl:uc:SubnetGroup"
    values = ["1"]
  }
}

data "aws_subnets" "tier2" {
  filter {
    name   = "vpc-id"
    values = [var.vpc_id]
  }
  filter {
    name   = "tag:exl:uc:SubnetGroup"
    values = ["2"]
  }
}

data "aws_subnets" "any" {
  filter {
    name   = "vpc-id"
    values = [var.vpc_id]
  }
}

locals {
  resolved_subnet_id = var.subnet_id != "" ? var.subnet_id : (
    length(data.aws_subnets.tier1.ids) > 0 ? sort(data.aws_subnets.tier1.ids)[0] : (
      length(data.aws_subnets.tier2.ids) > 0 ? sort(data.aws_subnets.tier2.ids)[0] : sort(data.aws_subnets.any.ids)[0]
    )
  )

  jumpbox_install_kubectl_effective = coalesce(var.jumpbox_install_kubectl, var.enable_eks_kubectl_iam)
  jumpbox_user_data = (
    local.jumpbox_install_kubectl_effective && var.eks_kubernetes_version != "" ?
    templatefile("${path.module}/templates/jumpbox-user-data.sh.tftpl", {
      kubernetes_version = var.eks_kubernetes_version
      helm_version       = var.jumpbox_helm_version
    }) : null
  )
}

data "aws_subnet" "selected" {
  id = local.resolved_subnet_id
}

resource "aws_iam_role" "ec2_ssm" {
  name = "${local.name_prefix}-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ec2.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })

  tags = {
    Name        = "${local.name_prefix}-role"
    Environment = var.environment
    AccountId   = var.aws_account_id
    ManagedBy   = "Terraform"
    Purpose     = "ec2-ssm-session-manager"
  }
}

resource "aws_iam_role_policy_attachment" "ssm_core" {
  role       = aws_iam_role.ec2_ssm.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

# Allows aws eks update-kubeconfig / aws eks get-token on the instance (private EKS API still requires VPC reachability).
resource "aws_iam_role_policy" "eks_kubectl" {
  count = var.enable_eks_kubectl_iam && var.eks_cluster_name != "" ? 1 : 0
  name  = "${local.name_prefix}-eks-kubectl"
  role  = aws_iam_role.ec2_ssm.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "EksDescribeClusterForKubeconfig"
        Effect = "Allow"
        Action = [
          "eks:DescribeCluster",
        ]
        Resource = "arn:aws:eks:${var.aws_region}:${var.aws_account_id}:cluster/${var.eks_cluster_name}"
      },
      {
        Sid      = "EksListClustersForCli"
        Effect   = "Allow"
        Action   = ["eks:ListClusters"]
        Resource = "*"
      },
    ]
  })
}

resource "aws_iam_role_policy" "s3_bucket_access" {
  count = length(var.s3_access_bucket_names) > 0 ? 1 : 0
  name  = "${local.name_prefix}-s3-bucket-access"
  role  = aws_iam_role.ec2_ssm.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "S3BucketsList"
        Effect = "Allow"
        Action = [
          "s3:ListBucket",
          "s3:GetBucketLocation",
        ]
        Resource = [for b in var.s3_access_bucket_names : "arn:aws:s3:::${b}"]
      },
      {
        Sid    = "S3ObjectsReadWrite"
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:AbortMultipartUpload",
          "s3:GetObjectVersion",
          "s3:ListBucketMultipartUploads",
          "s3:ListMultipartUploadParts",
        ]
        Resource = [for b in var.s3_access_bucket_names : "arn:aws:s3:::${b}/*"]
      },
    ]
  })
}

resource "aws_iam_instance_profile" "ec2_ssm" {
  name = "${local.name_prefix}-profile"
  role = aws_iam_role.ec2_ssm.name

  tags = {
    Name        = "${local.name_prefix}-profile"
    Environment = var.environment
    ManagedBy   = "Terraform"
  }
}

resource "aws_security_group" "this" {
  name        = "${local.name_prefix}-sg"
  description = "SSM-only test instance - no inbound; HTTPS (and HTTP) egress for SSM and package mirrors"
  vpc_id      = var.vpc_id

  egress {
    description = "HTTPS for SSM, AWS APIs, and TLS package mirrors"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    description = "HTTP for legacy package mirrors (optional)"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    description = "HTTP 8080 to EKS pods for SSM port-forward tunnelling"
    from_port   = 8080
    to_port     = 8080
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    description = "TCP 8000 to ALB/NLB backend service for SSM port-forward testing"
    from_port   = 8000
    to_port     = 8000
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    description = "TCP 8001 to ALB/NLB graph service for SSM port-forward testing"
    from_port   = 8001
    to_port     = 8001
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name        = "${local.name_prefix}-sg"
    Environment = var.environment
    AccountId   = var.aws_account_id
    ManagedBy   = "Terraform"
    Purpose     = "ec2-ssm-test"
  }
}

resource "aws_instance" "this" {
  ami                         = data.aws_ami.ubuntu.id
  instance_type               = var.instance_type
  subnet_id                   = local.resolved_subnet_id
  vpc_security_group_ids      = [aws_security_group.this.id]
  iam_instance_profile        = aws_iam_instance_profile.ec2_ssm.name
  associate_public_ip_address = false

  user_data                   = local.jumpbox_user_data
  user_data_replace_on_change = local.jumpbox_user_data != null

  # CKV_AWS_126: enable EC2 detailed (1-minute) CloudWatch monitoring.
  monitoring = true

  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 1
  }

  root_block_device {
    volume_type = "gp3"
    volume_size = var.root_volume_size_gb
    encrypted   = true
    # Fortify "Insecure EC2 Storage": optionally pin to a customer-managed KMS
    # key. Null falls back to AWS-managed EBS default key (current dev
    # behaviour; acceptable for a non-data-bearing bastion).
    kms_key_id            = var.root_volume_kms_key_arn != "" ? var.root_volume_kms_key_arn : null
    delete_on_termination = true
  }

  tags = {
    Name         = local.name_prefix
    Environment  = var.environment
    AccountId    = var.aws_account_id
    ManagedBy    = "Terraform"
    Purpose      = "ssm-test-instance"
    OS           = "Ubuntu-22.04-LTS"
    SubnetChoice = var.subnet_id != "" ? "explicit" : "auto-tier1-or-fallback"
  }
}

moved {
  from = aws_instance.this
  to   = aws_instance.windows_ssm_test
}

# Private Windows Server 2022 test instance with SSM Session Manager (no public RDP ingress).
# Fleet Manager Remote Desktop: Systems Manager > Fleet Manager > Managed nodes > instance >
#   Node actions > Connect > Remote Desktop (needs SSM Agent 3.0.222.0+ and console IAM for ssm-guiconnect).
# PowerShell session: EC2 > Connect > Session Manager.
# Requires SSM reachability from the subnet (VPC endpoints or corporate egress to AWS APIs on 443).
#
# MIDAS default: pass shared_jumpbox_* from module ec2-ssm-test so this instance uses the same
# IAM instance profile and security group as the Ubuntu jumpbox (i-0342e59b40cd01082 pattern).
#
# The module-owned IAM role, instance profile, and security group below are always created
# (count = 1) even in shared jumpbox mode. When shared_jumpbox_* is set, the instance does not
# use them; they stay as unused resources so Terraform never tries to destroy them in the same
# apply as an instance replacement (which would otherwise form a dependency cycle with the
# deposed EC2 object still referencing the old profile/SG).

locals {
  name_prefix = "midas-${var.environment}-ec2-ssm-windows-test"

  use_shared_jumpbox = (
    var.shared_jumpbox_security_group_id != "" &&
    var.shared_jumpbox_instance_profile_name != ""
  )

  trimmed_eks_kubernetes_version = trimspace(var.eks_kubernetes_version)

  # dl.k8s.io expects a full semver (e.g. v1.30.0). EKS often returns "1.30" only.
  # Placeholder when unset; only used in user_data when EKS client install runs (then version is non-empty).
  kubectl_download_semver = (
    local.trimmed_eks_kubernetes_version == "" ? "0.0.0" :
    length(regexall("^[0-9]+\\.[0-9]+$", local.trimmed_eks_kubernetes_version)) > 0 ?
    "${local.trimmed_eks_kubernetes_version}.0" :
    local.trimmed_eks_kubernetes_version
  )

  install_eks_tools_in_user_data = (
    var.bootstrap_install_eks_cli &&
    var.eks_cluster_name != "" &&
    local.trimmed_eks_kubernetes_version != ""
  )

  windows_bootstrap_script = var.enable_fleet_manager_bootstrap ? templatefile("${path.module}/templates/windows-fleet-eks-prep.ps1.tftpl", {
    kubernetes_version      = local.kubectl_download_semver
    enable_eks_client_tools = local.install_eks_tools_in_user_data
  }) : ""

  windows_user_data = var.enable_fleet_manager_bootstrap && local.windows_bootstrap_script != "" ? join("", [
    "<powershell>\n",
    local.windows_bootstrap_script,
    "\n</powershell>\n<persist>false</persist>\n",
  ]) : null
}

# Latest Amazon-managed Windows Server 2022 Full Base image (x86_64).
data "aws_ssm_parameter" "windows_2022_base" {
  name = "/aws/service/ami-windows-latest/Windows_Server-2022-English-Full-Base"
}

data "aws_subnet" "selected" {
  id = var.subnet_id
}

resource "terraform_data" "shared_jumpbox_pair" {
  lifecycle {
    precondition {
      condition = (
        (var.shared_jumpbox_security_group_id == "") == (var.shared_jumpbox_instance_profile_name == "")
      )
      error_message = "Set both shared_jumpbox_security_group_id and shared_jumpbox_instance_profile_name, or leave both empty."
    }
  }
}

data "aws_security_group" "shared_jumpbox" {
  count = local.use_shared_jumpbox ? 1 : 0
  id    = var.shared_jumpbox_security_group_id
}

data "aws_iam_instance_profile" "shared_jumpbox" {
  count = local.use_shared_jumpbox ? 1 : 0
  name  = var.shared_jumpbox_instance_profile_name
}

resource "aws_iam_role" "ec2_ssm_windows" {
  count = 1
  name  = "${local.name_prefix}-role"

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
    Purpose     = "ec2-ssm-windows-session-manager"
  }
}

resource "aws_iam_role_policy_attachment" "ssm_core" {
  count      = 1
  role       = aws_iam_role.ec2_ssm_windows[0].name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

# Mirrors ec2-ssm-test inline policy (eks:DescribeCluster + eks:ListClusters only) when this module owns the role.
resource "aws_iam_role_policy" "instance_inline" {
  count = (
    !local.use_shared_jumpbox &&
    var.enable_eks_kubectl_iam &&
    var.eks_cluster_name != ""
  ) ? 1 : 0
  name = "${local.name_prefix}-eks-kubectl"
  role = aws_iam_role.ec2_ssm_windows[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "EksDescribeClusterForKubeconfig"
        Effect   = "Allow"
        Action   = ["eks:DescribeCluster"]
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

resource "aws_iam_instance_profile" "ec2_ssm_windows" {
  count = 1
  name  = "${local.name_prefix}-profile"
  role  = aws_iam_role.ec2_ssm_windows[0].name

  depends_on = [
    aws_iam_role_policy_attachment.ssm_core,
    aws_iam_role_policy.instance_inline,
  ]

  tags = {
    Name        = "${local.name_prefix}-profile"
    Environment = var.environment
    ManagedBy   = "Terraform"
  }
}

resource "aws_security_group" "this" {
  count       = 1
  name        = "${local.name_prefix}-sg"
  description = "SSM-only Windows test instance - no inbound; egress for SSM, Windows Update, and AWS APIs"
  vpc_id      = var.vpc_id

  egress {
    description = "HTTPS for SSM, AWS APIs, Windows Update, KMS"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    description = "HTTP for optional redirects / legacy endpoints"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    description = "HTTP 8080 for SSM port-forward tunnelling to pods"
    from_port   = 8080
    to_port     = 8080
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    description = "TCP 8000 to ALB or NLB backends for SSM port-forward testing"
    from_port   = 8000
    to_port     = 8000
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    description = "TCP 8001 to graph service for SSM port-forward testing"
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
    Purpose     = "ec2-ssm-windows-test"
  }
}

resource "aws_instance" "windows_ssm_test" {
  ami                         = data.aws_ssm_parameter.windows_2022_base.value
  instance_type               = var.instance_type
  subnet_id                   = var.subnet_id
  key_name                    = var.key_name != "" ? var.key_name : null
  vpc_security_group_ids      = local.use_shared_jumpbox ? [var.shared_jumpbox_security_group_id] : [aws_security_group.this[0].id]
  iam_instance_profile        = local.use_shared_jumpbox ? var.shared_jumpbox_instance_profile_name : aws_iam_instance_profile.ec2_ssm_windows[0].name
  associate_public_ip_address = false

  user_data                   = local.windows_user_data
  user_data_replace_on_change = local.windows_user_data != null

  depends_on = [terraform_data.shared_jumpbox_pair]

  monitoring = false

  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 1
  }

  root_block_device {
    volume_type           = "gp3"
    volume_size           = var.root_volume_size_gb
    encrypted             = true
    delete_on_termination = true
  }

  tags = {
    Name          = local.name_prefix
    Environment   = var.environment
    AccountId     = var.aws_account_id
    Region        = var.aws_region
    ManagedBy     = "Terraform"
    Purpose       = "ssm-windows-test-instance"
    OS            = "Windows_Server-2022-English-Full-Base"
    ConnectVia    = "SessionManagerAndFleetManagerRDP"
    MidasWorkload = "private-test-vm"
  }

  lifecycle {
    precondition {
      condition     = data.aws_subnet.selected.vpc_id == var.vpc_id
      error_message = "subnet_id must belong to vpc_id (use the same VPC as the EKS cluster)."
    }

    precondition {
      condition = (
        !local.use_shared_jumpbox ||
        data.aws_security_group.shared_jumpbox[0].vpc_id == data.aws_subnet.selected.vpc_id
      )
      error_message = "shared_jumpbox_security_group_id must belong to the same VPC as subnet_id (use the ec2-ssm-test SG from the same VPC)."
    }
  }
}

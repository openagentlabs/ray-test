locals {
  env_config = {
    dev = {
      enable_lb  = true
      create_acm = true
      import_acm = false
    }
    qa = {
      enable_lb  = false
      create_acm = false
      import_acm = true
    }
    dev-stable = {
      enable_lb  = false
      create_acm = true
      import_acm = false
    }
  }

  ##################################################
  #     Subnet allocation and filtering
  ##################################################
  # This is a clever way of finding the largest subnet per availability zone in AWS
  # The caveat here is we need to remember to add ignore lifecycle changes to the 
  # subnet ids in the modules that use this data.
  # Subnet allocation and filtering
  subnets_struct = [
    for subnet in data.aws_subnet.selected_azs :
    {
      id        = subnet["id"]
      az        = subnet["availability_zone"]
      available = subnet["available_ip_address_count"]
    }
  ]

  azs = distinct([for s in local.subnets_struct : s.az])

  largest_per_az = [
    for az in local.azs : (
      reverse(sort([
        for s in local.subnets_struct :
        format("%08d|%s", s.available, s.id)
      if s.az == az]))[0]
    )
  ]

  eks_subnet_ids = [
    for s in local.largest_per_az :
    split("|", s)[1]
  ]

  #######################################################
  #     Cognito SAML metadata
  #######################################################
  saml_metadata = jsondecode(data.aws_secretsmanager_secret_version.cognito_sso_credentials.secret_string)["metadata"]
  #######################################################

  current    = local.env_config[var.environment]
  account_id = data.aws_caller_identity.current.account_id
  aws_region = data.aws_region.current.region

  eks_oidc_url = replace(one(one(aws_eks_cluster.exlerate_eks_cluster.identity).oidc).issuer, "https://", "")
  eks_cluster_managed_policy_arns = [
    "arn:aws:iam::aws:policy/AmazonEKSClusterPolicy",
    "arn:aws:iam::aws:policy/AmazonEKSVPCResourceController",
    "arn:aws:iam::aws:policy/AWSSecretsManagerClientReadOnlyAccess",
    "arn:aws:iam::aws:policy/AmazonS3ReadOnlyAccess"
  ]

  node_group_policy_arns = [
    "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly",
    "arn:aws:iam::aws:policy/AmazonEKS_CNI_Policy",
    "arn:aws:iam::aws:policy/AmazonEKSWorkerNodePolicy",
    "arn:aws:iam::aws:policy/service-role/AmazonEBSCSIDriverPolicy"
  ]

  karpenter_node_policies = [
    "arn:aws:iam::aws:policy/AmazonEKSWorkerNodePolicy",
    "arn:aws:iam::aws:policy/AmazonEKS_CNI_Policy",
    "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly"
  ]

  # Jenkins Subnet needed for 10.90.12.0/24
  ingress_rules_eks = [
    {
      from_port   = 2181
      to_port     = 2181
      protocol    = "tcp"
      cidr_blocks = [var.vpc_cidrs] # internal cluster CIDRs
      description = "ClickHouse Keeper TCP for probes"
    },
    {
      from_port   = 9182
      to_port     = 9182
      protocol    = "tcp"
      cidr_blocks = [var.vpc_cidrs]
      description = "ClickHouse Keeper HTTP for probes"
    },
    {
      from_port   = 443
      to_port     = 443
      protocol    = "tcp"
      cidr_blocks = [var.vpc_cidrs, "10.90.12.0/24", "10.54.5.10/32"]
      description = "To allow HTTPS access"
    },
    {
      from_port   = 2049
      to_port     = 2049
      protocol    = "tcp"
      cidr_blocks = [var.vpc_cidrs, "10.90.12.0/24"]
      description = "To allow EFS access"
    },
    {
      from_port   = 9443
      to_port     = 9443
      protocol    = "tcp"
      cidr_blocks = [var.vpc_cidrs, "10.90.12.0/24"]
      description = "To allow access to AWS Controller"
    },
    {
      from_port   = 10250
      to_port     = 10250
      protocol    = "tcp"
      cidr_blocks = [var.vpc_cidrs, "10.90.12.0/24"]
      description = "To allow access to Kubelet"
    },
    {
      from_port   = 4000
      to_port     = 4000
      protocol    = "tcp"
      cidr_blocks = [var.vpc_cidrs, "10.90.12.0/24"]
      description = "LiteLLM container port"
    },
    {
      from_port   = 3000
      to_port     = 3000
      protocol    = "tcp"
      cidr_blocks = [var.vpc_cidrs, "10.90.12.0/24"]
      description = "Langfuse Kubernetes ALB health checks and traffic"
    },
    {
      from_port   = 9001
      to_port     = 9001
      protocol    = "tcp"
      cidr_blocks = [var.vpc_cidrs, "10.90.12.0/24"]
      description = "C1 API container port - ALB health checks and traffic"
    },
    {
      from_port   = 30369
      to_port     = 30369
      protocol    = "tcp"
      cidr_blocks = [var.vpc_cidrs, "10.90.12.0/24"]
      description = "LiteLLM Kubernetes NodePort - ALB health checks and traffic"
    }
  ]

  egress_rules_eks = [
    {
      from_port   = 0
      to_port     = 0
      protocol    = "-1"
      cidr_blocks = ["0.0.0.0/0"]
      description = "To allow outbound access to all traffic"
    }
  ]

  ingress_rules_ng = [
    # Allow internal pod-to-pod / kubelet traffic to Keeper
    {
      from_port   = 2181
      to_port     = 2181
      protocol    = "tcp"
      cidr_blocks = [var.vpc_cidrs] # internal cluster CIDRs
      description = "ClickHouse Keeper TCP for probes"
    },
    {
      from_port   = 9182
      to_port     = 9182
      protocol    = "tcp"
      cidr_blocks = [var.vpc_cidrs]
      description = "ClickHouse Keeper HTTP for probes"
    },
    {
      from_port   = 8123
      to_port     = 8123
      protocol    = "tcp"
      cidr_blocks = [var.vpc_cidrs]
      description = "ClickHouse server port"
    },
    {
      from_port   = 22
      to_port     = 22
      protocol    = "tcp"
      cidr_blocks = [var.vpc_cidrs, "10.90.12.0/24"]
      description = "To allow SSH access"
    },
    {
      from_port   = 443
      to_port     = 443
      protocol    = "tcp"
      cidr_blocks = [var.vpc_cidrs, "10.90.12.0/24"]
      description = "To allow HTTPS access"
    },
    {
      from_port   = 9443
      to_port     = 9443
      protocol    = "tcp"
      cidr_blocks = [var.vpc_cidrs, "10.90.12.0/24"]
      description = "To allow access to AWS Controller"
    },
    {
      from_port   = 2049
      to_port     = 2049
      protocol    = "tcp"
      cidr_blocks = [var.vpc_cidrs, "10.90.12.0/24"]
      description = "To allow EFS access"
    },
    {
      from_port   = 10250
      to_port     = 10250
      protocol    = "tcp"
      cidr_blocks = [var.vpc_cidrs, "10.90.12.0/24"]
      description = "To allow access to Kubelet"
    },
    { # Litellm port
      from_port   = 4000
      to_port     = 4000
      protocol    = "tcp"
      cidr_blocks = [var.vpc_cidrs, "10.90.12.0/24"]
      description = "LiteLLM container port"
    },
    { # Langfuse port
      from_port   = 3000
      to_port     = 3000
      protocol    = "tcp"
      cidr_blocks = [var.vpc_cidrs, "10.90.12.0/24"]
      description = "Langfuse Kubernetes NodePort - ALB health checks and traffic"
    },
    { # C1 API port
      from_port   = 9001
      to_port     = 9001
      protocol    = "tcp"
      cidr_blocks = [var.vpc_cidrs, "10.90.12.0/24"]
      description = "C1 API Kubernetes NodePort - ALB health checks and traffic"
    },
    {
      from_port   = 30369
      to_port     = 30369
      protocol    = "tcp"
      cidr_blocks = [var.vpc_cidrs, "10.90.12.0/24"]
      description = "LiteLLM Kubernetes NodePort - ALB health checks and traffic"
    },
  ]
  egress_rules_ng = [
    {
      from_port   = 0
      to_port     = 0
      protocol    = "-1"
      cidr_blocks = ["0.0.0.0/0"]
      description = "To allow outbound access to all traffic"
    }
  ]

  alb_ingress_rules_litellm = [
    {
      from_port   = 443
      to_port     = 443
      protocol    = "tcp"
      cidr_blocks = var.litellm_alb_cidr_blocks
      description = "To allow HTTPS access"
    },
    {
      from_port   = 80
      to_port     = 80
      protocol    = "tcp"
      cidr_blocks = var.litellm_alb_cidr_blocks
      description = "To allow HTTP access"
    },
    {
      from_port   = 5432
      to_port     = 5432
      protocol    = "tcp"
      cidr_blocks = var.litellm_db_cidr_blocks
      description = "To allow PostgreSQL access"
    }
  ]

  alb_ingress_rules_langfuse = [
    {
      from_port   = 443
      to_port     = 443
      protocol    = "tcp"
      cidr_blocks = var.langfuse_alb_cidr_blocks
      description = "To allow HTTPS access"
    },
    {
      from_port   = 3000
      to_port     = 3000
      protocol    = "tcp"
      cidr_blocks = ["10.0.0.0/8"]
      description = "To allow Langfuse Web access"
    }
  ]

  alb_ingress_rules_c1_api = [
    {
      from_port   = 443
      to_port     = 443
      protocol    = "tcp"
      cidr_blocks = var.c1_api_alb_cidr_blocks
      description = "To allow HTTPS access"
    },
    {
      from_port   = 80
      to_port     = 80
      protocol    = "tcp"
      cidr_blocks = var.c1_api_alb_cidr_blocks
      description = "To allow HTTP access"
    },
    {
      from_port   = 8000
      to_port     = 8000
      protocol    = "tcp"
      cidr_blocks = var.c1_api_alb_cidr_blocks
      description = "To allow healthcheck access to control-api"
    },
    {
      from_port   = 9001
      to_port     = 9001
      protocol    = "tcp"
      cidr_blocks = var.c1_api_alb_cidr_blocks
      description = "To allow HTTP access to control-api"
    },
    {
      from_port   = 5432
      to_port     = 5432
      protocol    = "tcp"
      cidr_blocks = var.c1_api_alb_cidr_blocks
      description = "To allow PostgreSQL access to control-api"
    }
  ]
}
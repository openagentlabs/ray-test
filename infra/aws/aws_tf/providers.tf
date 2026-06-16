terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    tls = {
      source  = "hashicorp/tls"
      version = "~> 4.0"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.30"
    }
    helm = {
      source  = "hashicorp/helm"
      version = "~> 2.14"
    }
  }
}

data "aws_eks_cluster" "eks" {
  count = var.containers_eks_enabled ? 1 : 0
  name  = local.containers_cluster_name_effective
}

provider "kubernetes" {
  alias = "eks"

  host                   = try(data.aws_eks_cluster.eks[0].endpoint, "https://127.0.0.1")
  cluster_ca_certificate = try(base64decode(data.aws_eks_cluster.eks[0].certificate_authority[0].data), "")

  exec {
    api_version = "client.authentication.k8s.io/v1beta1"
    command     = "aws"
    args = [
      "eks",
      "get-token",
      "--cluster-name",
      local.containers_cluster_name_effective,
      "--region",
      local.solution.region,
    ]
    env = {
      AWS_PROFILE = "kt-acc"
    }
  }
}

provider "helm" {
  alias = "eks"

  kubernetes {
    host                   = try(data.aws_eks_cluster.eks[0].endpoint, "https://127.0.0.1")
    cluster_ca_certificate = try(base64decode(data.aws_eks_cluster.eks[0].certificate_authority[0].data), "")

    exec {
      api_version = "client.authentication.k8s.io/v1beta1"
      command     = "aws"
      args = [
        "eks",
        "get-token",
        "--cluster-name",
        local.containers_cluster_name_effective,
        "--region",
        local.solution.region,
      ]
      env = {
        AWS_PROFILE = "kt-acc"
      }
    }
  }
}

# Credentials: profile ``kt-acc`` in ~/.aws/credentials (synced from
# ``infra/envs/dev/.env.aws`` via ``make/load-aws-creds.sh``).
provider "aws" {
  region              = local.solution.region
  profile             = "kt-acc"
  allowed_account_ids = [local.solution.account_id]

  default_tags {
    tags = {
      AccountId             = local.solution.account_id
      Application           = local.solution_slug
      AutomationIgnore      = var.automation_ignore ? "true" : "false"
      CostCenter            = length(trimspace(var.cost_center)) > 0 ? var.cost_center : var.cost_code
      CostCode              = var.cost_code
      CreatedBy             = var.created_by
      Department            = var.department
      DeployedAt            = var.deployed_at
      DeployedBy            = var.deployed_by
      DeploymentEnvironment = var.deployment_environment
      DeploymentIndex       = var.deployment_index
      DeploymentInstance    = var.deployment_instance
      DeploymentKey         = local.deployment_key
      Description           = local.solution.description
      Environment           = var.deployment_environment
      ExpiresAt             = trimspace(var.expires_at)
      ManagedBy             = "Terraform"
      OwnerEmail            = var.owner_email
      Project               = local.solution.name
      ProjectId             = local.project_id
      ReleaseDate           = local.solution.date
      ResourceGroup1        = trimspace(var.resource_group_1)
      ResourceGroup2        = trimspace(var.resource_group_2)
      ResourceGroup3        = trimspace(var.resource_group_3)
      ResourceOwner         = var.resource_owner
      Version               = local.solution.version
    }
  }
}

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
  }
}

data "aws_eks_cluster_auth" "eks" {
  count = var.containers_eks_enabled ? 1 : 0
  name  = module.workloads_infra[0].cluster_name
}

provider "kubernetes" {
  alias = "eks"

  host                   = try(module.workloads_infra[0].cluster_endpoint, "https://127.0.0.1")
  cluster_ca_certificate = try(base64decode(module.workloads_infra[0].cluster_certificate_authority_data), "")
  token                  = try(data.aws_eks_cluster_auth.eks[0].token, "")
}

# Credentials: profile ``kt-acc`` in ~/.aws/credentials (synced from
# ``infra/envs/dev/.env.aws`` via ``make/load-aws-creds.sh``).
provider "aws" {
  region              = local.solution.region
  profile             = "kt-acc"
  allowed_account_ids = [local.solution.account_id]

  default_tags {
    tags = {
      Description = local.solution.description
      ManagedBy   = "Terraform"
      Project     = local.solution.name
      ReleaseDate = local.solution.date
      Version     = local.solution.version
    }
  }
}

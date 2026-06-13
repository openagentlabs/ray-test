terraform {
  # check blocks (checks-secretsmanager-rds.tf) require Terraform 1.5+.
  required_version = ">= 1.5"

  required_providers {
    aws = {
      source = "hashicorp/aws"
      # >= 6.19.0 required for aws_lb_listener_rule transform/url-rewrite block
      # (ALB modify-request-path support added in provider v6.19.0, Oct 2025).
      # EKS access entries require 5.33+; both constraints satisfied by >= 6.19.0.
      version = ">= 6.19.0"
    }
    random = {
      source  = "hashicorp/random"
      version = ">= 3.5.0"
    }
    tls = {
      source  = "hashicorp/tls"
      version = ">= 4.0.0"
    }
    # Required until remote state no longer tracks removed local_sensitive_file (Windows keypair); then drop this block.
    local = {
      source  = "hashicorp/local"
      version = ">= 2.5.0"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.27"
    }
    helm = {
      source  = "hashicorp/helm"
      version = "~> 2.13"
    }
  }

  backend "s3" {
    # -backend-config="bucket=${TERRAFORM_STATE_BUCKET}"
    # -backend-config="key=app-deploy-omf-${TENANT_ENV}/${TENANT_ID}/terraform.tfstate"
    # -backend-config="region=us-east-1"
  }
}

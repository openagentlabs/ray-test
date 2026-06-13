terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.27.0"
    }
  }
  # NOTE (MIDAS in-tree fork): the upstream version.tf has an empty `backend "s3" {}` block.
  # Terragrunt v0.48 generates `backend.tf` in this directory at init time, which conflicts
  # with the empty block (Terraform fails with "Duplicate backend configuration"). The MIDAS
  # overlay's terragrunt.hcl owns backend config; we drop the empty block here so Terragrunt
  # is the single source of truth for the S3 backend.
  required_version = "~> 1.5.0"
}

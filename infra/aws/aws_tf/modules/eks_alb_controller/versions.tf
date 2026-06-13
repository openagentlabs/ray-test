terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0"
    }
    helm = {
      source                = "hashicorp/helm"
      version               = ">= 2.14"
      configuration_aliases = [helm.eks]
    }
  }
}

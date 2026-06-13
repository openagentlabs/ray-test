terraform {
  required_providers {
    helm = {
      source                = "hashicorp/helm"
      version               = ">= 2.14"
      configuration_aliases = [helm.eks]
    }
    kubernetes = {
      source                = "hashicorp/kubernetes"
      version               = ">= 2.30"
      configuration_aliases = [kubernetes.eks]
    }
  }
}

provider "aws" {
  default_tags {
    tags = {
      BU       = var.BU
      CostCode = var.costcode
      Owner    = var.owner
      region   = "us-east-1"
      Backup   = "N"
    }
  }
  ignore_tags {
    key_prefixes = ["karpenter.sh/discovery"]
  }
}

data "aws_eks_cluster_auth" "exlerate_eks_cluster" {
  name = aws_eks_cluster.exlerate_eks_cluster.name
}

provider "kubernetes" {
  host                   = aws_eks_cluster.exlerate_eks_cluster.endpoint
  cluster_ca_certificate = base64decode(aws_eks_cluster.exlerate_eks_cluster.certificate_authority[0].data)
  token                  = data.aws_eks_cluster_auth.exlerate_eks_cluster.token
  exec { # This basically refreshes the EKS token if needed by TF
    api_version = "client.authentication.k8s.io/v1beta1"
    args        = ["eks", "get-token", "--cluster-name", var.eks_cluster_name]
    command     = "aws"
  }
}

provider "helm" {
  kubernetes = {
    host                   = aws_eks_cluster.exlerate_eks_cluster.endpoint
    cluster_ca_certificate = base64decode(aws_eks_cluster.exlerate_eks_cluster.certificate_authority[0].data)
    token                  = data.aws_eks_cluster_auth.exlerate_eks_cluster.token
  }
}


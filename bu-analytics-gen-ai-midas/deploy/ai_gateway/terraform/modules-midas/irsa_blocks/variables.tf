variable "eks_oidc_url" {
  type = string
}

variable "eks_cluster_name" {
  type = string
}

variable "account_id" {
  type = string
}

variable "application" {
  type = string
}

variable "eks_namespace" {
  type = string
}

variable "irsa_account_name" {
  type = string
}

variable "policy_arns" {
  type = list(string)
  default = [
    "arn:aws:iam::aws:policy/AmazonSSMReadOnlyAccess",
    "arn:aws:iam::aws:policy/AWSSecretsManagerClientReadOnlyAccess",
    "arn:aws:iam::aws:policy/AmazonS3ReadOnlyAccess"
  ]
}

variable "image_pull_secrets" {
  type    = list(string)
  default = []
}
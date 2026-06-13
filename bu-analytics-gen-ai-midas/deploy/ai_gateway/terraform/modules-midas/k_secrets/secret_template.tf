variable "metadataName" {
  type = string
}

variable "ns" {
  type = string
}

variable "secretName" {
  type = string
}

variable "secretValue" {
  type = string
}

resource "kubernetes_secret_v1" "k_secret_template" {
  metadata {
    name      = var.metadataName
    namespace = var.ns
  }

  data = {
    "${var.secretName}" = var.secretValue
  }

  type = "Opaque"
}
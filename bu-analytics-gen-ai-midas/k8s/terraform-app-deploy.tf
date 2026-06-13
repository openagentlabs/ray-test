terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = ">= 2.20"
    }
  }
}

variable "aws_region" {
  type    = string
  default = "us-east-1"
}

variable "aws_profile" {
  type    = string
  default = "saiyam-arora"
}

variable "cluster_name" {
  type        = string
  description = "Existing EKS cluster name"
  default     = "midas-eks"
}

variable "namespace" {
  type    = string
  default = "midas-saiyam"
}

variable "backend_image" {
  type        = string
  description = "Full backend image URI including tag"
  default     = "882884688997.dkr.ecr.us-east-1.amazonaws.com/midas-backend:2026-03-17-1"
}

variable "frontend_image" {
  type        = string
  description = "Full frontend image URI including tag"
  default     = "882884688997.dkr.ecr.us-east-1.amazonaws.com/midas-frontend:2026-03-17-1"
}

variable "backend_upstream" {
  type        = string
  description = "Frontend -> backend service URL"
  default     = "http://midas-backend.midas-saiyam.svc.cluster.local:8000"
}

variable "backend_node_selector" {
  type    = map(string)
  default = { "midas-role" = "backend" }
}

variable "frontend_node_selector" {
  type    = map(string)
  default = { "midas-role" = "frontend" }
}

variable "backend_secret_data" {
  type        = map(string)
  description = "Secret key/value pairs for backend runtime"
  sensitive   = true
  default = {
    ENDPOINT           = "https://midas-genai-coe-268728.cognitiveservices.azure.com/openai/deployments/gpt-4.1-nano/chat/completions?api-version=2025-01-01-preview"
    API_KEY            = "REPLACE_WITH_AZURE_OPENAI_API_KEY"
    MODEL              = "gpt-4.1-nano"
    EMBEDDING_MODEL    = "text-embedding-ada-002"
    EMBEDDING_ENDPOINT = "https://midas-genai-coe-268728.cognitiveservices.azure.com/openai/deployments/text-embedding-ada-002/embeddings?api-version=2023-05-15"
    API_KEY_EMBEDDING  = "REPLACE_WITH_AZURE_OPENAI_EMBEDDING_API_KEY"
    AZURE_KG_ENDPOINT  = "https://midas-genai-coe-268728.cognitiveservices.azure.com/openai/deployments/gpt-4.1-mini/chat/completions?api-version=2025-01-01-preview"
    KG_MODEL           = "gpt-4.1-mini"
  }
}

provider "aws" {
  region  = var.aws_region
  profile = var.aws_profile
}

data "aws_eks_cluster" "target" {
  name = var.cluster_name
}

data "aws_eks_cluster_auth" "target" {
  name = var.cluster_name
}

provider "kubernetes" {
  host                   = data.aws_eks_cluster.target.endpoint
  cluster_ca_certificate = base64decode(data.aws_eks_cluster.target.certificate_authority[0].data)
  token                  = data.aws_eks_cluster_auth.target.token
}

resource "kubernetes_namespace_v1" "app" {
  metadata {
    name = var.namespace
  }
}

resource "kubernetes_secret_v1" "backend" {
  metadata {
    name      = "midas-backend-secrets"
    namespace = kubernetes_namespace_v1.app.metadata[0].name
  }

  type = "Opaque"
  data = var.backend_secret_data
}

resource "kubernetes_deployment_v1" "backend" {
  metadata {
    name      = "midas-backend"
    namespace = kubernetes_namespace_v1.app.metadata[0].name
    labels = {
      app = "midas-backend"
    }
  }

  spec {
    replicas = 1

    strategy {
      type = "RollingUpdate"
      rolling_update {
        max_surge       = "0"
        max_unavailable = "1"
      }
    }

    selector {
      match_labels = {
        app = "midas-backend"
      }
    }

    template {
      metadata {
        labels = {
          app = "midas-backend"
        }
      }

      spec {
        node_selector = var.backend_node_selector

        container {
          name              = "backend"
          image             = var.backend_image
          image_pull_policy = "Always"

          port {
            container_port = 8000
          }

          env {
            name = "ENDPOINT"
            value_from {
              secret_key_ref {
                name = kubernetes_secret_v1.backend.metadata[0].name
                key  = "ENDPOINT"
              }
            }
          }

          env {
            name = "API_KEY"
            value_from {
              secret_key_ref {
                name = kubernetes_secret_v1.backend.metadata[0].name
                key  = "API_KEY"
              }
            }
          }

          env {
            name = "MODEL"
            value_from {
              secret_key_ref {
                name = kubernetes_secret_v1.backend.metadata[0].name
                key  = "MODEL"
              }
            }
          }

          env {
            name = "EMBEDDING_MODEL"
            value_from {
              secret_key_ref {
                name = kubernetes_secret_v1.backend.metadata[0].name
                key  = "EMBEDDING_MODEL"
              }
            }
          }

          env {
            name = "EMBEDDING_ENDPOINT"
            value_from {
              secret_key_ref {
                name = kubernetes_secret_v1.backend.metadata[0].name
                key  = "EMBEDDING_ENDPOINT"
              }
            }
          }

          env {
            name = "API_KEY_EMBEDDING"
            value_from {
              secret_key_ref {
                name = kubernetes_secret_v1.backend.metadata[0].name
                key  = "API_KEY_EMBEDDING"
              }
            }
          }

          env {
            name = "AZURE_KG_ENDPOINT"
            value_from {
              secret_key_ref {
                name = kubernetes_secret_v1.backend.metadata[0].name
                key  = "AZURE_KG_ENDPOINT"
              }
            }
          }

          env {
            name = "KG_MODEL"
            value_from {
              secret_key_ref {
                name = kubernetes_secret_v1.backend.metadata[0].name
                key  = "KG_MODEL"
              }
            }
          }

          readiness_probe {
            http_get {
              path = "/health"
              port = 8000
            }
            initial_delay_seconds = 15
            period_seconds        = 10
          }

          liveness_probe {
            http_get {
              path = "/health"
              port = 8000
            }
            initial_delay_seconds = 30
            period_seconds        = 20
          }
        }
      }
    }
  }
}

resource "kubernetes_service_v1" "backend" {
  metadata {
    name      = "midas-backend"
    namespace = kubernetes_namespace_v1.app.metadata[0].name
    labels = {
      app = "midas-backend"
    }
  }

  spec {
    selector = {
      app = "midas-backend"
    }

    port {
      name        = "http"
      port        = 8000
      target_port = 8000
      protocol    = "TCP"
    }

    type = "ClusterIP"
  }
}

resource "kubernetes_deployment_v1" "frontend" {
  metadata {
    name      = "midas-frontend"
    namespace = kubernetes_namespace_v1.app.metadata[0].name
    labels = {
      app = "midas-frontend"
    }
  }

  spec {
    replicas = 1

    strategy {
      type = "RollingUpdate"
      rolling_update {
        max_surge       = "0"
        max_unavailable = "1"
      }
    }

    selector {
      match_labels = {
        app = "midas-frontend"
      }
    }

    template {
      metadata {
        labels = {
          app = "midas-frontend"
        }
      }

      spec {
        node_selector = var.frontend_node_selector

        container {
          name              = "frontend"
          image             = var.frontend_image
          image_pull_policy = "Always"

          port {
            container_port = 80
          }

          env {
            name  = "BACKEND_UPSTREAM"
            value = var.backend_upstream
          }

          readiness_probe {
            http_get {
              path = "/"
              port = 80
            }
            initial_delay_seconds = 10
            period_seconds        = 10
          }

          liveness_probe {
            http_get {
              path = "/"
              port = 80
            }
            initial_delay_seconds = 20
            period_seconds        = 20
          }
        }
      }
    }
  }
}

resource "kubernetes_service_v1" "frontend" {
  metadata {
    name      = "midas-frontend"
    namespace = kubernetes_namespace_v1.app.metadata[0].name
    labels = {
      app = "midas-frontend"
    }
  }

  spec {
    selector = {
      app = "midas-frontend"
    }

    port {
      name        = "http"
      port        = 80
      target_port = 80
      protocol    = "TCP"
    }

    type = "ClusterIP"
  }
}

output "namespace" {
  value = kubernetes_namespace_v1.app.metadata[0].name
}

output "backend_service" {
  value = kubernetes_service_v1.backend.metadata[0].name
}

output "frontend_service" {
  value = kubernetes_service_v1.frontend.metadata[0].name
}

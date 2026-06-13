resource "helm_release" "ray_cluster" {
  provider = helm.eks

  name       = local.cluster_release_name
  repository = "https://ray-project.github.io/kuberay-helm/"
  chart      = "ray-cluster"
  version    = var.chart_version
  namespace  = var.namespace
  wait       = true
  timeout    = 900

  values = [
    yamlencode({
      fullnameOverride = local.cluster_release_name

      image = {
        repository = var.ray_image_repository
        tag        = var.ray_image_tag
        pullPolicy = "IfNotPresent"
      }

      service = {
        type = "ClusterIP"
      }

      common = local.shared_mount_common_overrides

      head = merge({
        rayVersion              = var.ray_image_tag
        enableInTreeAutoscaling = true
        rayStartParams = {
          "dashboard-host" = "0.0.0.0"
          "num-cpus"       = "2"
        }
        resources = {
          limits = {
            cpu    = "2"
            memory = "8Gi"
          }
          requests = {
            cpu    = "2"
            memory = "8Gi"
          }
        }
        nodeSelector = {
          (var.node_pool_label_key) = var.node_pool_label_value
        }
        volumes = concat([
          {
            name     = "log-volume"
            emptyDir = {}
          },
          {
            name = "dshm"
            emptyDir = {
              medium = "Memory"
            }
          },
          ], var.lustre_mount_enabled ? [
          {
            name = var.lustre_volume_name
            persistentVolumeClaim = {
              claimName = var.lustre_volume_name
            }
          },
          ] : [], var.s3_shared_mount_enabled ? [
          {
            name = var.s3_shared_volume_name
            persistentVolumeClaim = {
              claimName = var.s3_shared_volume_name
            }
          },
        ] : [], local.shared_mount_health_enabled ? [local.shared_mount_health_volume] : [])
        volumeMounts = concat([
          {
            mountPath = "/tmp/ray"
            name      = "log-volume"
          },
          {
            mountPath = "/dev/shm"
            name      = "dshm"
          },
          ], var.lustre_mount_enabled ? [
          {
            mountPath = var.lustre_mount_path
            name      = var.lustre_volume_name
          },
          ] : [], var.s3_shared_mount_enabled ? [
          {
            mountPath = var.s3_shared_mount_path
            name      = var.s3_shared_volume_name
          },
        ] : [])
      }, local.shared_mount_health_pod_overrides)

      worker = merge({
        replicas    = var.worker_min_replicas
        minReplicas = var.worker_min_replicas
        maxReplicas = var.worker_max_replicas
        rayStartParams = {
          "num-cpus" = "6"
        }
        resources = {
          limits = {
            cpu    = "6"
            memory = "24Gi"
          }
          requests = {
            cpu    = "6"
            memory = "24Gi"
          }
        }
        nodeSelector = {
          (var.node_pool_label_key) = var.node_pool_label_value
        }
        volumes = concat([
          {
            name     = "log-volume"
            emptyDir = {}
          },
          {
            name = "dshm"
            emptyDir = {
              medium = "Memory"
            }
          },
          ], var.lustre_mount_enabled ? [
          {
            name = var.lustre_volume_name
            persistentVolumeClaim = {
              claimName = var.lustre_volume_name
            }
          },
          ] : [], var.s3_shared_mount_enabled ? [
          {
            name = var.s3_shared_volume_name
            persistentVolumeClaim = {
              claimName = var.s3_shared_volume_name
            }
          },
        ] : [], local.shared_mount_health_enabled ? [local.shared_mount_health_volume] : [])
        volumeMounts = concat([
          {
            mountPath = "/tmp/ray"
            name      = "log-volume"
          },
          {
            mountPath = "/dev/shm"
            name      = "dshm"
          },
          ], var.lustre_mount_enabled ? [
          {
            mountPath = var.lustre_mount_path
            name      = var.lustre_volume_name
          },
          ] : [], var.s3_shared_mount_enabled ? [
          {
            mountPath = var.s3_shared_mount_path
            name      = var.s3_shared_volume_name
          },
        ] : [])
        topologySpreadConstraints = [
          {
            maxSkew           = 1
            topologyKey       = "kubernetes.io/hostname"
            whenUnsatisfiable = "ScheduleAnyway"
            labelSelector = {
              matchLabels = {
                "ray.io/node-type" = "worker"
              }
            }
          },
        ]
      }, local.shared_mount_health_pod_overrides)
    }),
  ]

  depends_on = [kubernetes_config_map.shared_mount_health]
}

resource "kubernetes_service" "ray_head_metrics" {
  provider = kubernetes.eks

  metadata {
    name      = "${local.cluster_release_name}-head-metrics"
    namespace = var.namespace
    labels = {
      "app.kubernetes.io/managed-by" = "terraform"
      "app.kubernetes.io/name"       = "ray-head-metrics"
      solution                       = var.solution.name
    }
  }

  spec {
    selector = {
      "ray.io/node-type" = "head"
      "ray.io/cluster"   = local.cluster_release_name
    }

    port {
      name        = "metrics"
      port        = 8080
      target_port = 8080
      protocol    = "TCP"
    }

    type = "ClusterIP"
  }

  depends_on = [helm_release.ray_cluster]
}

resource "kubernetes_ingress_v1" "ray_dashboard" {
  provider = kubernetes.eks

  metadata {
    name      = "${local.cluster_release_name}-dashboard"
    namespace = var.namespace
    annotations = {
      "alb.ingress.kubernetes.io/scheme"           = "internet-facing"
      "alb.ingress.kubernetes.io/target-type"      = "ip"
      "alb.ingress.kubernetes.io/group.name"       = var.alb_ingress_group_name
      "alb.ingress.kubernetes.io/listen-ports"     = "[{\"HTTP\": 80}]"
      "alb.ingress.kubernetes.io/healthcheck-path" = "/"
    }
    labels = {
      "app.kubernetes.io/managed-by" = "terraform"
      "app.kubernetes.io/name"       = "ray-dashboard"
      solution                       = var.solution.name
    }
  }

  spec {
    ingress_class_name = var.ingress_class

    rule {
      http {
        path {
          path      = "/"
          path_type = "Prefix"
          backend {
            service {
              name = local.head_service_name
              port {
                number = 8265
              }
            }
          }
        }

        path {
          path      = "/metrics"
          path_type = "Prefix"
          backend {
            service {
              name = kubernetes_service.ray_head_metrics.metadata[0].name
              port {
                number = 8080
              }
            }
          }
        }
      }
    }
  }

  depends_on = [
    helm_release.ray_cluster,
    kubernetes_service.ray_head_metrics,
  ]
}

data "kubernetes_ingress_v1" "ray_dashboard" {
  provider = kubernetes.eks

  metadata {
    name      = kubernetes_ingress_v1.ray_dashboard.metadata[0].name
    namespace = var.namespace
  }

  depends_on = [kubernetes_ingress_v1.ray_dashboard]
}

resource "helm_release" "fsx_csi" {
  provider = helm.eks

  name             = "aws-fsx-csi-driver"
  repository       = "https://kubernetes-sigs.github.io/aws-fsx-csi-driver"
  chart            = "aws-fsx-csi-driver"
  version          = var.chart_version
  namespace        = "kube-system"
  create_namespace = false
  wait             = true
  timeout          = 900

  values = [
    yamlencode({
      controller = {
        serviceAccount = {
          create = true
          name   = local.service_account_name
          annotations = {
            "eks.amazonaws.com/role-arn" = aws_iam_role.fsx_csi.arn
          }
        }
      }
      node = {
        tolerateAllTaints = true
        # DaemonSet must not schedule on Fargate (hostPath + NodeAffinity); only Ray EC2 nodes.
        nodeSelector = {
          (var.node_pool_label_key) = var.node_pool_label_value
        }
        serviceAccount = {
          create = true
          name   = "fsx-csi-node-sa"
        }
      }
    }),
  ]

  depends_on = [aws_iam_role_policy_attachment.fsx_csi]
}

resource "kubernetes_persistent_volume" "shared_lustre" {
  provider = kubernetes.eks

  for_each = local.mount_namespaces

  metadata {
    name = "${local.volume_name}-${each.key}"
    labels = {
      "app.kubernetes.io/managed-by" = "terraform"
      "app.kubernetes.io/name"       = local.volume_name
      solution                       = var.solution.name
    }
  }

  spec {
    capacity = {
      storage = "${var.storage_capacity_gib}Gi"
    }
    access_modes                     = ["ReadWriteMany"]
    persistent_volume_reclaim_policy = "Retain"
    storage_class_name               = ""
    mount_options                    = ["flock"]

    persistent_volume_source {
      csi {
        driver        = "fsx.csi.aws.com"
        volume_handle = var.file_system_id
        volume_attributes = {
          dnsname   = var.file_system_dns_name
          mountname = var.file_system_mount_name
        }
      }
    }
  }

  depends_on = [helm_release.fsx_csi]
}

resource "kubernetes_persistent_volume_claim" "shared_lustre" {
  provider = kubernetes.eks

  for_each = local.mount_namespaces

  metadata {
    name      = local.volume_name
    namespace = each.key
    labels = {
      "app.kubernetes.io/managed-by" = "terraform"
      "app.kubernetes.io/name"       = local.volume_name
      solution                       = var.solution.name
    }
  }

  spec {
    access_modes       = ["ReadWriteMany"]
    storage_class_name = ""
    volume_name        = kubernetes_persistent_volume.shared_lustre[each.key].metadata[0].name

    resources {
      requests = {
        storage = "${var.storage_capacity_gib}Gi"
      }
    }
  }

  depends_on = [kubernetes_persistent_volume.shared_lustre]
}

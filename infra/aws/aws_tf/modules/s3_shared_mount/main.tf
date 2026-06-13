resource "aws_eks_addon" "mountpoint_s3_csi" {
  cluster_name                = var.cluster_name
  addon_name                  = "aws-mountpoint-s3-csi-driver"
  addon_version               = length(trimspace(var.addon_version)) > 0 ? var.addon_version : null
  service_account_role_arn    = aws_iam_role.s3_csi.arn
  resolve_conflicts_on_create = "OVERWRITE"
  resolve_conflicts_on_update = "OVERWRITE"

  tags = {
    purpose   = "eks-mountpoint-s3-csi"
    cluster   = var.cluster_name
    Component = "shared-s3-files"
    Service   = "platform"
  }

  depends_on = [aws_iam_role_policy_attachment.s3_csi]
}

resource "kubernetes_persistent_volume" "shared_s3_files" {
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
      storage = "${var.storage_request_gib}Gi"
    }
    access_modes                     = ["ReadWriteMany"]
    persistent_volume_reclaim_policy = "Retain"
    storage_class_name               = ""
    mount_options                    = local.mount_options

    claim_ref {
      namespace = each.key
      name      = local.volume_name
    }

    persistent_volume_source {
      csi {
        driver        = "s3.csi.aws.com"
        volume_handle = "${var.bucket_name}-${each.key}"
        volume_attributes = {
          bucketName = var.bucket_name
        }
      }
    }
  }

  depends_on = [aws_eks_addon.mountpoint_s3_csi]
}

resource "kubernetes_persistent_volume_claim" "shared_s3_files" {
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
    volume_name        = kubernetes_persistent_volume.shared_s3_files[each.key].metadata[0].name

    resources {
      requests = {
        storage = "${var.storage_request_gib}Gi"
      }
    }
  }

  depends_on = [kubernetes_persistent_volume.shared_s3_files]
}

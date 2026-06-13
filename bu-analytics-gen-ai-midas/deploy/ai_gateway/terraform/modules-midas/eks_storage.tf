# # Necessary storage class definitions needed for ClickHouse
resource "kubernetes_storage_class_v1" "clickhouse-server-gp3" {
  metadata {
    name = "clickhouse-server-${var.eks_cluster_name}"
    labels = {
      type = "clickhouse-server"
    }
  }

  storage_provisioner    = "ebs.csi.aws.com"
  reclaim_policy         = "Retain"
  volume_binding_mode    = "WaitForFirstConsumer"
  allow_volume_expansion = true

  parameters = {
    type      = "gp3"
    fsType    = "ext4"
    encrypted = true
  }
}

resource "kubernetes_storage_class_v1" "clickhouse-keeper-gp3" {
  metadata {
    name = "clickhouse-keeper-${var.eks_cluster_name}"
    labels = {
      type = "clickhouse-keeper"
    }
  }

  storage_provisioner    = "ebs.csi.aws.com"
  reclaim_policy         = "Retain" # Was Retain but cloud rules revert back to delete anyway
  volume_binding_mode    = "WaitForFirstConsumer"
  allow_volume_expansion = true

  parameters = {
    type      = "gp3"
    fsType    = "ext4"
    encrypted = true
  }
}
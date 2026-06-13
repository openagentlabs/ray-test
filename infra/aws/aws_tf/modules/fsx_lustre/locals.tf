locals {
  is_persistent = contains(["PERSISTENT_1", "PERSISTENT_2"], var.deployment_type)

  file_system_name = replace(replace(replace(lower(replace(
    "${var.solution.name}-${var.purpose}",
    "_",
    "-",
  )), "--", "-"), "--", "-"), "--", "-")

  module_tags = merge(
    {
      "fsx:Purpose"      = var.purpose
      Service            = "platform"
      Component          = "shared-lustre"
      DataClassification = "internal"
      Backup             = var.automatic_backup_retention_days > 0 ? "enabled" : "disabled"
      Criticality        = "high"
    },
    var.additional_tags,
  )

  lustre_client_ports = [
    { from = 988, to = 988, description = "Lustre rpcbind" },
    { from = 1021, to = 1023, description = "Lustre data/metadata" },
  ]
}

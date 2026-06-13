###############################################################################
# infra/tf_lib/fsx_lustre — FSx for Lustre file system
#
# Based on hashicorp/aws aws_fsx_lustre_file_system:
# https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/fsx_lustre_file_system
#
# Security group rules adapted from terraform-aws-modules/fsx/aws//modules/lustre v1.3.1
###############################################################################

data "aws_subnet" "primary" {
  count = var.create ? 1 : 0

  id = var.subnet_ids[0]
}

resource "aws_security_group" "lustre" {
  count = var.create ? 1 : 0

  name_prefix = "${substr(local.file_system_name, 0, 40)}-"
  description = "FSx for Lustre client access for ${local.file_system_name}"
  vpc_id      = data.aws_subnet.primary[0].vpc_id

  tags = merge(
    local.module_tags,
    {
      Name = "${local.file_system_name}-sg"
    },
  )

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_vpc_security_group_ingress_rule" "lustre_vpc" {
  for_each = var.create ? { for idx, port in local.lustre_client_ports : tostring(idx) => port } : {}

  security_group_id = aws_security_group.lustre[0].id
  ip_protocol       = "tcp"
  from_port         = each.value.from
  to_port           = each.value.to
  cidr_ipv4         = var.vpc_cidr_block
  description       = each.value.description
}

resource "aws_vpc_security_group_ingress_rule" "lustre_self" {
  for_each = var.create ? { for idx, port in local.lustre_client_ports : "self-${idx}" => port } : {}

  security_group_id            = aws_security_group.lustre[0].id
  ip_protocol                  = "tcp"
  from_port                    = each.value.from
  to_port                      = each.value.to
  referenced_security_group_id = aws_security_group.lustre[0].id
  description                  = "Lustre traffic between FSx file servers"
}

resource "aws_vpc_security_group_ingress_rule" "lustre_workload_sgs" {
  for_each = var.create && length(var.workload_security_group_ids) > 0 ? {
    for pair in setproduct(range(length(var.workload_security_group_ids)), range(length(local.lustre_client_ports))) :
    "${pair[0]}-${pair[1]}" => {
      security_group_id = var.workload_security_group_ids[pair[0]]
      port              = local.lustre_client_ports[pair[1]]
    }
  } : {}

  security_group_id            = aws_security_group.lustre[0].id
  ip_protocol                  = "tcp"
  from_port                    = each.value.port.from
  to_port                      = each.value.port.to
  referenced_security_group_id = each.value.security_group_id
  description                  = "Lustre client access from EKS workload security groups"
}

resource "aws_vpc_security_group_egress_rule" "lustre_all" {
  count = var.create ? 1 : 0

  security_group_id = aws_security_group.lustre[0].id
  ip_protocol       = "-1"
  cidr_ipv4         = "0.0.0.0/0"
  description       = "Allow outbound for FSx management traffic"
}

resource "aws_fsx_lustre_file_system" "this" {
  count = var.create ? 1 : 0

  automatic_backup_retention_days = local.is_persistent ? var.automatic_backup_retention_days : null
  data_compression_type             = var.data_compression_type
  deployment_type                   = var.deployment_type
  per_unit_storage_throughput       = local.is_persistent ? var.per_unit_storage_throughput : null
  security_group_ids                = [aws_security_group.lustre[0].id]
  storage_capacity                  = var.storage_capacity
  storage_type                      = local.is_persistent ? var.storage_type : null
  subnet_ids                        = [var.subnet_ids[0]]

  tags = merge(
    local.module_tags,
    {
      Name = local.file_system_name
    },
  )
}

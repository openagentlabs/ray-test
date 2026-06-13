locals {
  solution_slug = replace(replace(replace(lower(replace(var.solution.name, "_", "-")), "--", "-"), "--", "-"), "--", "-")
  name_prefix   = local.solution_slug

  use_existing = var.existing_vpc_id != "" && length(var.existing_subnet_ids) >= 2
  vpc_id       = local.use_existing ? var.existing_vpc_id : aws_vpc.this[0].id

  azs = slice(data.aws_availability_zones.available.names, 0, var.availability_zone_count)

  cluster_tag = var.cluster_name != "" ? {
    "kubernetes.io/cluster/${var.cluster_name}" = "shared"
  } : {}

  alb_public_subnet_ids  = local.use_existing ? var.existing_subnet_ids : aws_subnet.alb_public[*].id
  eks_private_subnet_ids = local.use_existing ? var.existing_subnet_ids : aws_subnet.eks_private[*].id
  bastion_subnet_ids     = local.use_existing ? var.existing_subnet_ids : aws_subnet.bastion[*].id
}

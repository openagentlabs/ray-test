data "aws_availability_zones" "available" {
  state = "available"
}

locals {
  use_existing      = var.existing_vpc_id != "" && length(var.existing_subnet_ids) >= 2
  vpc_id            = local.use_existing ? var.existing_vpc_id : aws_vpc.this[0].id
  public_subnet_ids = local.use_existing ? var.existing_subnet_ids : aws_subnet.public[*].id
}

resource "aws_vpc" "this" {
  count = local.use_existing ? 0 : 1

  cidr_block           = var.vpc_cidr
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = {
    Name    = "${lower(replace(var.solution.name, "_", "-"))}-${var.solution.deployment_key}-eks"
    purpose = "eks-fargate"
  }
}

resource "aws_internet_gateway" "this" {
  count = local.use_existing ? 0 : 1

  vpc_id = aws_vpc.this[0].id

  tags = {
    Name    = "${lower(replace(var.solution.name, "_", "-"))}-${var.solution.deployment_key}-eks-igw"
    purpose = "eks-fargate"
  }
}

resource "aws_subnet" "public" {
  count = local.use_existing ? 0 : 2

  vpc_id                  = aws_vpc.this[0].id
  cidr_block              = cidrsubnet(var.vpc_cidr, 8, count.index)
  availability_zone       = data.aws_availability_zones.available.names[count.index]
  map_public_ip_on_launch = true

  tags = merge(
    {
      Name    = "${lower(replace(var.solution.name, "_", "-"))}-${var.solution.deployment_key}-eks-public-${count.index + 1}"
      purpose = "eks-fargate-public"
    },
    var.cluster_name != "" ? {
      "kubernetes.io/cluster/${var.cluster_name}" = "shared"
      "kubernetes.io/role/elb"                    = "1"
    } : {},
  )
}

resource "aws_route_table" "public" {
  count = local.use_existing ? 0 : 1

  vpc_id = aws_vpc.this[0].id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.this[0].id
  }

  tags = {
    Name    = "${var.solution.name}-eks-public-rt"
    purpose = "eks-fargate"
  }
}

resource "aws_route_table_association" "public" {
  count = local.use_existing ? 0 : length(aws_subnet.public)

  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public[0].id
}

resource "aws_subnet" "private" {
  count = 2

  vpc_id                  = local.vpc_id
  cidr_block              = cidrsubnet(var.vpc_cidr, 8, count.index + 2)
  availability_zone       = data.aws_availability_zones.available.names[count.index]
  map_public_ip_on_launch = false

  tags = merge(
    {
      Name    = "${var.solution.name}-eks-private-${count.index + 1}"
      purpose = "eks-fargate-private"
    },
    var.cluster_name != "" ? {
      "kubernetes.io/cluster/${var.cluster_name}" = "shared"
      "kubernetes.io/role/internal-elb"           = "1"
    } : {},
  )
}

resource "aws_eip" "nat" {
  domain = "vpc"

  tags = {
    Name    = "${var.solution.name}-eks-nat-eip"
    purpose = "eks-fargate"
  }
}

resource "aws_nat_gateway" "this" {
  allocation_id = aws_eip.nat.id
  subnet_id     = local.public_subnet_ids[0]

  tags = {
    Name    = "${var.solution.name}-eks-nat"
    purpose = "eks-fargate"
  }

  depends_on = [aws_internet_gateway.this]
}

resource "aws_route_table" "private" {
  vpc_id = local.vpc_id

  route {
    cidr_block     = "0.0.0.0/0"
    nat_gateway_id = aws_nat_gateway.this.id
  }

  tags = {
    Name    = "${var.solution.name}-eks-private-rt"
    purpose = "eks-fargate"
  }
}

resource "aws_route_table_association" "private" {
  count = 2

  subnet_id      = aws_subnet.private[count.index].id
  route_table_id = aws_route_table.private.id
}

resource "aws_ec2_tag" "existing_subnet_cluster" {
  for_each = local.use_existing && var.cluster_name != "" ? toset(var.existing_subnet_ids) : toset([])

  resource_id = each.value
  key         = "kubernetes.io/cluster/${var.cluster_name}"
  value       = "shared"
}

resource "aws_ec2_tag" "existing_subnet_elb" {
  for_each = local.use_existing && var.cluster_name != "" ? toset(var.existing_subnet_ids) : toset([])

  resource_id = each.value
  key         = "kubernetes.io/role/elb"
  value       = "1"
}

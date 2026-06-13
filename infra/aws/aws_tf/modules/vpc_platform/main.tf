data "aws_availability_zones" "available" {
  state = "available"
}

resource "aws_vpc" "this" {
  count = local.use_existing ? 0 : 1

  cidr_block           = var.vpc_cidr
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = {
    Name      = "${local.name_prefix}-platform"
    purpose   = "platform-vpc"
    Component = "network"
    Service   = "platform"
  }
}

resource "aws_internet_gateway" "this" {
  count = local.use_existing ? 0 : 1

  vpc_id = aws_vpc.this[0].id

  tags = {
    Name    = "${local.name_prefix}-igw"
    purpose = "platform-igw"
  }
}

# Public subnets — internet-facing Application Load Balancers
resource "aws_subnet" "alb_public" {
  count = local.use_existing ? 0 : var.availability_zone_count

  vpc_id                  = aws_vpc.this[0].id
  cidr_block              = cidrsubnet(var.vpc_cidr, 8, count.index)
  availability_zone       = local.azs[count.index]
  map_public_ip_on_launch = true

  tags = merge(
    {
      Name      = "${local.name_prefix}-alb-public-${count.index + 1}"
      purpose   = "alb-public"
      Component = "network"
      Service   = "platform"
    },
    local.cluster_tag,
    {
      "kubernetes.io/role/elb" = "1"
    },
  )
}

# Private subnets — EKS Fargate workloads (no public IPs)
resource "aws_subnet" "eks_private" {
  count = local.use_existing ? 0 : var.availability_zone_count

  vpc_id            = aws_vpc.this[0].id
  cidr_block        = cidrsubnet(var.vpc_cidr, 8, count.index + 10)
  availability_zone = local.azs[count.index]

  tags = merge(
    {
      Name      = "${local.name_prefix}-eks-private-${count.index + 1}"
      purpose   = "eks-private"
      Component = "network"
      Service   = "platform"
    },
    local.cluster_tag,
    {
      "kubernetes.io/role/internal-elb" = "1"
    },
  )
}

# Private subnets — bastion / break-glass hosts (SSM Session Manager; no inbound SSH)
resource "aws_subnet" "bastion" {
  count = local.use_existing ? 0 : var.availability_zone_count

  vpc_id            = aws_vpc.this[0].id
  cidr_block        = cidrsubnet(var.vpc_cidr, 8, count.index + 20)
  availability_zone = local.azs[count.index]

  tags = {
    Name      = "${local.name_prefix}-bastion-${count.index + 1}"
    purpose   = "bastion-private"
    Component = "network"
    Service   = "platform"
  }
}

resource "aws_eip" "nat" {
  count = local.use_existing ? 0 : (var.single_nat_gateway_enabled ? 1 : var.availability_zone_count)

  domain = "vpc"

  tags = {
    Name    = "${local.name_prefix}-nat-eip-${count.index + 1}"
    purpose = "platform-nat"
  }

  depends_on = [aws_internet_gateway.this]
}

resource "aws_nat_gateway" "this" {
  count = local.use_existing ? 0 : (var.single_nat_gateway_enabled ? 1 : var.availability_zone_count)

  allocation_id = aws_eip.nat[count.index].id
  subnet_id     = aws_subnet.alb_public[count.index].id

  tags = {
    Name    = "${local.name_prefix}-nat-${count.index + 1}"
    purpose = "platform-nat"
  }

  depends_on = [aws_internet_gateway.this]
}

resource "aws_route_table" "alb_public" {
  count = local.use_existing ? 0 : 1

  vpc_id = aws_vpc.this[0].id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.this[0].id
  }

  tags = {
    Name    = "${local.name_prefix}-alb-public-rt"
    purpose = "alb-public"
  }
}

resource "aws_route_table_association" "alb_public" {
  count = local.use_existing ? 0 : length(aws_subnet.alb_public)

  subnet_id      = aws_subnet.alb_public[count.index].id
  route_table_id = aws_route_table.alb_public[0].id
}

resource "aws_route_table" "private" {
  count = local.use_existing ? 0 : var.availability_zone_count

  vpc_id = aws_vpc.this[0].id

  route {
    cidr_block     = "0.0.0.0/0"
    nat_gateway_id = var.single_nat_gateway_enabled ? aws_nat_gateway.this[0].id : aws_nat_gateway.this[count.index].id
  }

  tags = {
    Name    = "${local.name_prefix}-private-rt-${count.index + 1}"
    purpose = "private"
  }
}

resource "aws_route_table_association" "eks_private" {
  count = local.use_existing ? 0 : length(aws_subnet.eks_private)

  subnet_id      = aws_subnet.eks_private[count.index].id
  route_table_id = aws_route_table.private[count.index].id
}

resource "aws_route_table_association" "bastion" {
  count = local.use_existing ? 0 : length(aws_subnet.bastion)

  subnet_id      = aws_subnet.bastion[count.index].id
  route_table_id = aws_route_table.private[count.index].id
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

# VPC endpoints — private connectivity for EKS Fargate and SSM bastion (no public internet required)
resource "aws_security_group" "vpc_endpoints" {
  count = local.use_existing || !var.vpc_endpoints_enabled ? 0 : 1

  name_prefix = "${local.name_prefix}-vpce-"
  description = "Interface VPC endpoints for ${local.name_prefix}"
  vpc_id      = local.vpc_id

  ingress {
    description = "HTTPS from VPC"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = [var.vpc_cidr]
  }

  egress {
    description = "All outbound"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name    = "${local.name_prefix}-vpc-endpoints"
    purpose = "vpc-endpoints"
  }
}

resource "aws_vpc_endpoint" "s3" {
  count = local.use_existing || !var.vpc_endpoints_enabled ? 0 : 1

  vpc_id       = local.vpc_id
  service_name = "com.amazonaws.${var.solution.region}.s3"
  route_table_ids = concat(
    aws_route_table.alb_public[*].id,
    aws_route_table.private[*].id,
  )

  tags = {
    Name    = "${local.name_prefix}-s3-gateway"
    purpose = "vpc-endpoint-s3"
  }
}

locals {
  interface_endpoint_services = [
    "ecr.api",
    "ecr.dkr",
    "logs",
    "ssm",
    "ssmmessages",
    "ec2messages",
    "sts",
  ]
}

resource "aws_vpc_endpoint" "interface" {
  for_each = local.use_existing || !var.vpc_endpoints_enabled ? toset([]) : toset(local.interface_endpoint_services)

  vpc_id              = local.vpc_id
  service_name        = "com.amazonaws.${var.solution.region}.${each.key}"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = aws_subnet.eks_private[*].id
  security_group_ids  = [aws_security_group.vpc_endpoints[0].id]
  private_dns_enabled = true

  tags = {
    Name    = "${local.name_prefix}-vpce-${replace(each.key, ".", "-")}"
    purpose = "vpc-endpoint-${each.key}"
  }
}

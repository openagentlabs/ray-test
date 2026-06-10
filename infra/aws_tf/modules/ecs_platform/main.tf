resource "aws_ecs_cluster" "this" {
  name = var.cluster_name

  setting {
    name  = "containerInsights"
    value = "disabled"
  }

  tags = {
    purpose = "arb-containers"
  }
}

resource "aws_service_discovery_private_dns_namespace" "this" {
  name        = var.service_discovery_namespace_name
  description = "Private DNS for ${var.solution.name} ECS workloads"
  vpc         = var.vpc_id

  tags = {
    purpose = "ecs-service-discovery"
  }
}

data "aws_iam_policy_document" "ecs_task_execution_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "execution" {
  name_prefix        = "${var.solution.name}-ecs-exec-"
  assume_role_policy = data.aws_iam_policy_document.ecs_task_execution_assume.json

  tags = {
    purpose = "ecs-task-execution"
  }
}

resource "aws_iam_role_policy_attachment" "execution_managed" {
  role       = aws_iam_role.execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_security_group" "tasks" {
  name_prefix = "${var.solution.name}-ecs-tasks-"
  description = "Shared security group for ARB ECS tasks (intra-stack gRPC + ALB frontend)."
  vpc_id      = var.vpc_id

  ingress {
    description = "Allow all task-to-task traffic within this security group"
    from_port   = 0
    to_port     = 65535
    protocol    = "tcp"
    self        = true
  }

  ingress {
    description = "Public HTTP to frontend tasks (when not behind ALB health checks only)"
    from_port   = 8802
    to_port     = 8802
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    purpose = "ecs-tasks"
  }
}

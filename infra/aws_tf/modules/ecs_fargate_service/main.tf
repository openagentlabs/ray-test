locals {
  environment_list = [
    for k, v in var.container_environment : {
      name  = k
      value = v
    }
  ]
}

resource "aws_cloudwatch_log_group" "task" {
  name              = "/ecs/${var.solution.name}/${var.workload_key}"
  retention_in_days = 14

  tags = {
    workload = var.workload_key
    purpose  = "ecs-container-logs"
  }
}

resource "aws_ecs_task_definition" "this" {
  family                   = "${var.solution.name}-${var.workload_key}"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.cpu
  memory                   = var.memory
  execution_role_arn       = var.execution_role_arn
  task_role_arn            = var.task_role_arn

  container_definitions = jsonencode([
    {
      name      = var.container_name
      image     = var.container_image
      essential = true
      portMappings = [
        {
          containerPort = var.container_port
          hostPort      = var.container_port
          protocol      = "tcp"
        },
      ]
      environment = local.environment_list
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = aws_cloudwatch_log_group.task.name
          awslogs-region        = var.solution.region
          awslogs-stream-prefix = var.workload_key
        }
      }
    },
  ])

  tags = {
    workload = var.workload_key
  }
}

resource "aws_service_discovery_service" "this" {
  name = var.service_discovery_name

  dns_config {
    namespace_id = var.service_discovery_namespace_id
    dns_records {
      ttl  = 10
      type = "A"
    }
    routing_policy = "MULTIVALUE"
  }

  health_check_custom_config {
    failure_threshold = 1
  }
}

resource "aws_lb" "public" {
  count = var.enable_public_alb ? 1 : 0

  name_prefix        = substr(replace(var.workload_key, "_", ""), 0, 6)
  load_balancer_type = "application"
  internal           = false
  security_groups    = [aws_security_group.alb[0].id]
  subnets            = var.subnet_ids

  tags = {
    workload = var.workload_key
    purpose  = "public-alb"
  }
}

resource "aws_security_group" "alb" {
  count = var.enable_public_alb ? 1 : 0

  name_prefix = "${var.solution.name}-alb-"
  description = "Internet-facing ALB for ${var.service_name}"
  vpc_id      = data.aws_vpc.selected.id

  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

data "aws_vpc" "selected" {
  id = data.aws_subnet.first.vpc_id
}

data "aws_subnet" "first" {
  id = var.subnet_ids[0]
}

resource "aws_lb_target_group" "this" {
  count = var.enable_public_alb ? 1 : 0

  name_prefix = substr(replace(var.workload_key, "_", ""), 0, 6)
  port        = var.container_port
  protocol    = "HTTP"
  vpc_id      = data.aws_vpc.selected.id
  target_type = "ip"

  health_check {
    path                = "/login"
    matcher             = "200-399"
    healthy_threshold   = 2
    unhealthy_threshold = 3
    interval            = 30
  }
}

resource "aws_lb_listener" "http" {
  count = var.enable_public_alb ? 1 : 0

  load_balancer_arn = aws_lb.public[0].arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.this[0].arn
  }
}

resource "aws_ecs_service" "this" {
  name            = var.service_name
  cluster         = var.cluster_arn
  task_definition = aws_ecs_task_definition.this.arn
  desired_count   = var.desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = var.subnet_ids
    security_groups  = [var.task_security_group_id]
    assign_public_ip = var.assign_public_ip
  }

  service_registries {
    registry_arn = aws_service_discovery_service.this.arn
  }

  dynamic "load_balancer" {
    for_each = var.enable_public_alb ? [1] : []
    content {
      target_group_arn = aws_lb_target_group.this[0].arn
      container_name   = var.container_name
      container_port   = var.container_port
    }
  }

  depends_on = [aws_lb_listener.http]

  tags = {
    workload = var.workload_key
  }
}

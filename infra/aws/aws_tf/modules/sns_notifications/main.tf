###############################################################################
# notification.svc — Amazon SNS topic for email-protocol notifications.
###############################################################################

terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0"
    }
  }
}

locals {
  _topic_name_raw = lower(replace(
    "${var.solution.name}-${var.solution.deployment_key}-notifications-email",
    "_",
    "-",
  ))
  topic_name = can(regex("--", var.solution.deployment_key)) ? local._topic_name_raw : replace(replace(replace(local._topic_name_raw, "--", "-"), "--", "-"), "--", "-")
}

resource "aws_sns_topic" "notifications" {
  name = local.topic_name

  tags = {
    solution    = var.solution.name
    description = var.solution.description
    version     = var.solution.version
    date        = var.solution.date
    account_id  = var.solution.account_id
    region      = var.solution.region
    purpose     = "notification-svc-email"
  }
}

resource "aws_sns_topic_subscription" "email" {
  for_each  = toset(var.email_subscription_endpoints)
  topic_arn = aws_sns_topic.notifications.arn
  protocol  = "email"
  endpoint  = each.value
}

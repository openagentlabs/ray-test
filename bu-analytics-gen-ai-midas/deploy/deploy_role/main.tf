terraform {
  required_version = ">= 1.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

# Trust policy plus ten customer-managed policies for midas-deployer-role.
#
# Files: midas-deployer-policy-001 .. midas-deployer-policy-010 (see .cursor/rules/solution_policy.mdc).
# AWS limits:
#   - Max 10 managed policies attached to a role (default quota) - this layout uses all 10 slots.
#   - Max 6,144 characters per customer-managed policy document (serialized JSON).
# fileset is scoped to midas-deployer-policy-* so stray files in iam-policy/ are not attached.
locals {
  trust_relationship = jsondecode(file("${path.module}/trust-relationship/trusted-entities.json"))

  policy_files = fileset("${path.module}/iam-policy", "midas-deployer-policy-*")

  policies = {
    for policy_file in local.policy_files :
    policy_file => jsondecode(file("${path.module}/iam-policy/${policy_file}"))
  }
}

resource "aws_iam_role" "deployer_role" {
  name               = var.role_name
  assume_role_policy = jsonencode(local.trust_relationship)
  tags               = var.tags
}

# One managed policy per midas-deployer-policy-* file (10 attachments; stay within per-policy size limit)
resource "aws_iam_policy" "deployer_policies" {
  for_each    = local.policies
  name        = "${var.role_name}-${each.key}"
  description = "Managed policy for ${var.role_name}: ${each.key}"
  policy      = jsonencode(each.value)
  tags        = var.tags
}

resource "aws_iam_role_policy_attachment" "deployer_policies" {
  for_each   = local.policies
  role       = aws_iam_role.deployer_role.name
  policy_arn = aws_iam_policy.deployer_policies[each.key].arn
}

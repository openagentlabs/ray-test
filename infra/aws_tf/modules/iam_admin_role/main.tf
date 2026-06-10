###############################################################################
# infra/aws_tf/modules/iam_admin_role — same-account admin role composition
#
# Trust is intentionally broad (`arn:aws:iam::<account>:root`). Tighten the
# trust policy here when you know which principals should assume this role.
###############################################################################

data "aws_iam_policy_document" "assume_same_account_root" {
  statement {
    sid     = "AssumeFromAccountRoot"
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "AWS"
      identifiers = ["arn:aws:iam::${var.solution.account_id}:root"]
    }
  }
}

module "role" {
  source = "../iam_role"

  solution                = var.solution
  role_name               = var.role_name
  assume_role_policy_json = data.aws_iam_policy_document.assume_same_account_root.json
  description             = "Full AWS administrator access via AWS managed AdministratorAccess; trust is limited by this module's policy document."
  managed_policy_arns     = ["arn:aws:iam::aws:policy/AdministratorAccess"]
  additional_tags = {
    "iam:AccessTier" = "administrator"
  }
}

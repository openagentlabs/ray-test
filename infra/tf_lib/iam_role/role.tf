###############################################################################
# infra/tf_lib/iam_role — IAM role (permissions added here or via ARNs)
###############################################################################

resource "aws_iam_role" "this" {
  name                 = var.role_name
  assume_role_policy   = var.assume_role_policy_json
  description          = var.description
  max_session_duration = var.max_session_duration
  path                 = var.path

  tags = merge(
    {
      "iam:RoleName" = var.role_name
      "SolutionName" = var.solution.name
    },
    var.additional_tags,
  )
}

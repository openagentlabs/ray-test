###############################################################################
# infra/tf_lib/iam_role — attach managed policies by ARN
###############################################################################

resource "aws_iam_role_policy_attachment" "managed" {
  for_each = toset(var.managed_policy_arns)

  role       = aws_iam_role.this.name
  policy_arn = each.value
}

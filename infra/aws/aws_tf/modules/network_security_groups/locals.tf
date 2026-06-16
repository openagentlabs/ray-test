locals {
  solution_slug = replace(replace(replace(lower(replace(var.solution.name, "_", "-")), "--", "-"), "--", "-"), "--", "-")
  _name_prefix_raw = lower(replace("${var.solution.name}-${var.solution.deployment_key}", "_", "-"))
  name_prefix      = can(regex("--", var.solution.deployment_key)) ? local._name_prefix_raw : replace(replace(replace(local._name_prefix_raw, "--", "-"), "--", "-"), "--", "-")
}

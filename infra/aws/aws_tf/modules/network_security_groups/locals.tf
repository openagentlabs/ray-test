locals {
  solution_slug = replace(replace(replace(lower(replace(var.solution.name, "_", "-")), "--", "-"), "--", "-"), "--", "-")
  name_prefix   = local.solution_slug
}

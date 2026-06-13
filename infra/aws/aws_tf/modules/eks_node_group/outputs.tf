output "node_group_name" {
  description = "Name of the EKS managed node group for Ray workloads."
  value       = aws_eks_node_group.ray.node_group_name
}

output "node_role_arn" {
  description = "IAM role ARN assumed by EC2 nodes in the Ray node group."
  value       = aws_iam_role.node.arn
}

output "node_pool_label_key" {
  description = "Node label key used to schedule Ray and demo pods."
  value       = var.node_pool_label_key
}

output "node_pool_label_value" {
  description = "Node label value for the Ray compute pool."
  value       = var.node_pool_label_value
}

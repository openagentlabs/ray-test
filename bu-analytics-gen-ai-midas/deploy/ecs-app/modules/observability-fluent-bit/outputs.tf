output "ecr_repository_url" {
  description = "Private ECR repository URL for the aws-for-fluent-bit image mirror. Mirror the public image here before the first apply."
  value       = aws_ecr_repository.fluent_bit.repository_url
}

output "ecr_repository_name" {
  description = "Private ECR repository name for the aws-for-fluent-bit image mirror."
  value       = aws_ecr_repository.fluent_bit.name
}

output "helm_release_name" {
  description = "Name of the Fluent Bit Helm release."
  value       = helm_release.fluent_bit.name
}

output "helm_release_namespace" {
  description = "Kubernetes namespace where Fluent Bit is deployed."
  value       = helm_release.fluent_bit.namespace
}

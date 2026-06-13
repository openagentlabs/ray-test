output "repository_arn" {
  description = "ARN of the ECR repository."
  value       = aws_ecr_repository.this.arn
}

output "repository_name" {
  description = "Name of the ECR repository."
  value       = aws_ecr_repository.this.name
}

output "repository_url" {
  description = "Registry URL for docker push/pull."
  value       = aws_ecr_repository.this.repository_url
}

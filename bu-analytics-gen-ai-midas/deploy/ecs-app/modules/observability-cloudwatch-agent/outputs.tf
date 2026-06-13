output "ecr_repository_url_agent" {
  description = "Private ECR repository URL for the cloudwatch-agent image mirror. Mirror the public image here before the first apply (see deploy/scripts/ci/mirror-addon-images-ecr.sh)."
  value       = aws_ecr_repository.cwagent.repository_url
}

output "ecr_repository_url_operator" {
  description = "Private ECR repository URL for the cloudwatch-agent-operator image mirror."
  value       = aws_ecr_repository.cwagent_operator.repository_url
}

output "ecr_repository_name_agent" {
  description = "Private ECR repository name for the cloudwatch-agent image mirror."
  value       = aws_ecr_repository.cwagent.name
}

output "ecr_repository_name_operator" {
  description = "Private ECR repository name for the cloudwatch-agent-operator image mirror."
  value       = aws_ecr_repository.cwagent_operator.name
}

output "irsa_role_arn" {
  description = "IAM role ARN assumed by the cloudwatch-agent service account via IRSA. CloudWatchAgentServerPolicy is attached."
  value       = aws_iam_role.cwagent.arn
}

output "irsa_role_name" {
  description = "IAM role name for the cloudwatch-agent IRSA role."
  value       = aws_iam_role.cwagent.name
}

output "helm_release_name" {
  description = "Name of the amazon-cloudwatch-observability Helm release."
  value       = helm_release.cloudwatch_observability.name
}

output "helm_release_namespace" {
  description = "Kubernetes namespace where the CloudWatch Agent and operator are deployed."
  value       = helm_release.cloudwatch_observability.namespace
}

output "container_insights_namespace" {
  description = "CloudWatch metric namespace where node/pod/container metrics appear (CloudWatch -> Metrics -> All metrics -> ContainerInsights)."
  value       = "ContainerInsights"
}

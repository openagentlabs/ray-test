output "opensearch_domain_endpoint" {
  description = "OpenSearch domain endpoint (VPC-private HTTPS). Use in Fluent Bit opensearch output host and in OpenSearch Dashboards."
  value       = aws_opensearch_domain.this.endpoint
}

output "opensearch_domain_arn" {
  description = "OpenSearch domain ARN."
  value       = aws_opensearch_domain.this.arn
}

output "opensearch_dashboards_url" {
  description = "OpenSearch Dashboards URL (VPC-private only)."
  value       = "https://${aws_opensearch_domain.this.endpoint}/_dashboards"
}

output "opensearch_write_policy_arn" {
  description = "ARN of the IAM policy granting es:ESHttpPost/Put. Attach to IRSA role if not using node-level attachment."
  value       = aws_iam_policy.opensearch_write.arn
}

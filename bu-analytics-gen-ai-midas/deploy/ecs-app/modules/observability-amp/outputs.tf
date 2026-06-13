output "amp_workspace_id" {
  description = "AMP workspace ID."
  value       = aws_prometheus_workspace.this.id
}

output "amp_workspace_arn" {
  description = "AMP workspace ARN."
  value       = aws_prometheus_workspace.this.arn
}

output "amp_remote_write_url" {
  description = "AMP Remote Write URL. Use in deploy/observability/otel-collector/values.yaml as exporters.prometheusremotewrite.endpoint."
  value       = "${aws_prometheus_workspace.this.prometheus_endpoint}api/v1/remote_write"
}

output "amp_query_endpoint" {
  description = "AMP Prometheus-compatible query endpoint. Use as the Grafana data source URL."
  value       = aws_prometheus_workspace.this.prometheus_endpoint
}

output "amp_remote_write_policy_arn" {
  description = "ARN of the IAM policy granting aps:RemoteWrite. Attach to IRSA service account role if not using node-level attachment."
  value       = aws_iam_policy.amp_remote_write.arn
}

output "docstore_attachments_bucket_name" {
  description = "S3 bucket for document-storage attachments."
  value       = aws_s3_bucket.docstore_attachments.id
}

output "docstore_attachments_bucket_arn" {
  description = "ARN of the docstore attachments bucket."
  value       = aws_s3_bucket.docstore_attachments.arn
}

output "docstore_opensearch_collection_name" {
  description = "OpenSearch Serverless collection for vector search."
  value       = aws_opensearchserverless_collection.docstore_vector.name
}

output "docstore_opensearch_collection_arn" {
  description = "ARN of the docstore OpenSearch collection."
  value       = aws_opensearchserverless_collection.docstore_vector.arn
}

output "docstore_opensearch_collection_endpoint" {
  description = "HTTPS endpoint for document-storage.svc OpenSearch Serverless vector search."
  value       = aws_opensearchserverless_collection.docstore_vector.collection_endpoint
}

output "test_bucket_id" {
  description = "Name of the MIDAS test S3 bucket (bucket_prefix suffix assigned by AWS)."
  value       = aws_s3_bucket.test.id
}

output "test_bucket_arn" {
  description = "ARN of the MIDAS test S3 bucket."
  value       = aws_s3_bucket.test.arn
}

###############################################################################
# document-storage.svc — OpenSearch Serverless vector search + attachments S3.
###############################################################################

locals {
  # OpenSearch Serverless names must be 3–32 characters.
  collection_name = substr(
    replace(replace(replace(lower(replace("${var.solution.name}-${var.solution.deployment_key}-doc-vec", "_", "-")), "--", "-"), "--", "-"), "--", "-"),
    0,
    32,
  )
  attachments_bucket_base = replace(replace(replace(lower(replace(
    "${var.solution.name}-${var.solution.deployment_key}-docstore-attachments-${var.solution.account_id}",
    "_",
    "-",
  )), "--", "-"), "--", "-"), "--", "-")
  attachments_bucket = trimsuffix(substr(local.attachments_bucket_base, 0, 63), "-")
}

resource "aws_s3_bucket" "docstore_attachments" {
  bucket = local.attachments_bucket

  tags = {
    "docstore:Purpose" = "attachments"
  }
}

resource "aws_s3_bucket_public_access_block" "docstore_attachments" {
  bucket = aws_s3_bucket.docstore_attachments.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_opensearchserverless_collection" "docstore_vector" {
  name = local.collection_name
  type = "VECTORSEARCH"

  tags = {
    "docstore:Purpose" = "vector-search"
  }

  depends_on = [
    aws_opensearchserverless_security_policy.docstore_encryption,
    aws_opensearchserverless_security_policy.docstore_network,
  ]
}

resource "aws_opensearchserverless_security_policy" "docstore_encryption" {
  name = substr("${local.collection_name}-enc", 0, 32)
  type = "encryption"

  policy = jsonencode({
    Rules = [
      {
        Resource     = ["collection/${local.collection_name}"]
        ResourceType = "collection"
      },
    ]
    AWSOwnedKey = true
  })
}

resource "aws_opensearchserverless_security_policy" "docstore_network" {
  name = substr("${local.collection_name}-net", 0, 32)
  type = "network"

  policy = jsonencode([
    {
      Rules = [
        {
          Resource     = ["collection/${local.collection_name}"]
          ResourceType = "collection"
        },
      ]
      AllowFromPublic = true
    },
  ])
}

resource "aws_opensearchserverless_access_policy" "docstore_data" {
  name = substr("${local.collection_name}-data", 0, 32)
  type = "data"

  policy = jsonencode([
    {
      Rules = [
        {
          Resource     = ["collection/${local.collection_name}"]
          ResourceType = "collection"
          Permission = [
            "aoss:CreateCollectionItems",
            "aoss:DeleteCollectionItems",
            "aoss:UpdateCollectionItems",
            "aoss:DescribeCollectionItems",
          ]
        },
        {
          Resource     = ["index/${local.collection_name}/*"]
          ResourceType = "index"
          Permission = [
            "aoss:CreateIndex",
            "aoss:DeleteIndex",
            "aoss:UpdateIndex",
            "aoss:DescribeIndex",
            "aoss:ReadDocument",
            "aoss:WriteDocument",
          ]
        },
      ]
      Principal = var.opensearch_principal_arns
    },
  ])
}

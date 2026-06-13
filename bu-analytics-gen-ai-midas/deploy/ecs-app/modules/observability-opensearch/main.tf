# MIDAS Amazon OpenSearch Service domain (Phase C — KQL log search)
#
# Creates a private OpenSearch domain inside the MIDAS VPC.
# Fluent Bit (already deployed as a DaemonSet) is extended with an
# opensearch output plugin to dual-write logs.
#
# Register in deploy/ecs-app/observability.tf:
#   module "observability_opensearch" {
#     count       = var.observability_opensearch_enabled ? 1 : 0
#     source      = "./modules/observability-opensearch"
#     environment = var.environment
#     vpc_id      = var.eks_vpc_id
#     subnet_ids  = var.eks_node_subnet_ids
#   }
#
# See docs/adr/0002-midas-kql-log-search.md for the decision record.

locals {
  domain_name = "midas-${var.environment}-logs"
}

# Security group for the OpenSearch domain — restricts access to the VPC CIDR.
resource "aws_security_group" "opensearch" {
  name        = "${local.domain_name}-sg"
  description = "Allow HTTPS 443 from the MIDAS VPC to OpenSearch."
  vpc_id      = var.vpc_id

  ingress {
    description = "HTTPS from VPC"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = [var.vpc_cidr]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(
    {
      Name        = "${local.domain_name}-sg"
      Environment = var.environment
      ManagedBy   = "terraform"
      Project     = "midas"
    },
    var.tags,
  )
}

resource "aws_opensearch_domain" "this" {
  # checkov:skip=CKV_AWS_318: Three dedicated master nodes more than double cluster cost and are not required for the dev observability domain. Toggle on for production via var.dedicated_master_enabled before promotion.
  domain_name    = local.domain_name
  engine_version = var.opensearch_version

  cluster_config {
    instance_type          = var.instance_type
    instance_count         = var.instance_count
    zone_awareness_enabled = var.instance_count > 1

    # CKV_AWS_318: optional dedicated master nodes — wired via var.dedicated_master_enabled.
    dedicated_master_enabled = var.dedicated_master_enabled
    dedicated_master_count   = var.dedicated_master_enabled ? var.dedicated_master_count : null
    dedicated_master_type    = var.dedicated_master_enabled ? var.dedicated_master_type : null
  }

  ebs_options {
    ebs_enabled = true
    volume_size = var.volume_size_gb
    volume_type = "gp3"
  }

  vpc_options {
    subnet_ids         = slice(var.subnet_ids, 0, var.instance_count > 1 ? 2 : 1)
    security_group_ids = [aws_security_group.opensearch.id]
  }

  encrypt_at_rest {
    enabled    = true
    kms_key_id = var.kms_key_arn != "" ? var.kms_key_arn : null
  }

  node_to_node_encryption {
    enabled = true
  }

  domain_endpoint_options {
    enforce_https       = true
    tls_security_policy = "Policy-Min-TLS-1-2-2019-07"
  }

  advanced_security_options {
    enabled                        = true
    internal_user_database_enabled = false
    master_user_options {
      master_user_arn = var.master_user_arn
    }
  }

  log_publishing_options {
    cloudwatch_log_group_arn = aws_cloudwatch_log_group.opensearch.arn
    log_type                 = "INDEX_SLOW_LOGS"
    enabled                  = true
  }

  # CKV_AWS_317: publish OpenSearch audit logs to the dedicated CloudWatch log group.
  log_publishing_options {
    cloudwatch_log_group_arn = aws_cloudwatch_log_group.opensearch.arn
    log_type                 = "AUDIT_LOGS"
    enabled                  = true
  }

  tags = merge(
    {
      Environment = var.environment
      ManagedBy   = "terraform"
      Project     = "midas"
      Component   = "observability-opensearch"
    },
    var.tags,
  )
}

resource "aws_cloudwatch_log_group" "opensearch" {
  name              = "/midas/${var.environment}/opensearch"
  retention_in_days = var.retention_in_days

  tags = merge(
    {
      Environment = var.environment
      ManagedBy   = "terraform"
      Project     = "midas"
    },
    var.tags,
  )
}

resource "aws_cloudwatch_log_resource_policy" "opensearch" {
  policy_name = "midas-${var.environment}-opensearch-log-policy"
  policy_document = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "es.amazonaws.com" }
      Action    = ["logs:PutLogEvents", "logs:CreateLogStream"]
      Resource  = "${aws_cloudwatch_log_group.opensearch.arn}:*"
    }]
  })
}

# IAM policy for Fluent Bit (EKS node role) to bulk-index to OpenSearch.
resource "aws_iam_policy" "opensearch_write" {
  name        = "midas-${var.environment}-opensearch-write"
  description = "Allow Fluent Bit DaemonSet to write logs to the MIDAS OpenSearch domain."

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "OpenSearchWrite"
        Effect = "Allow"
        Action = [
          "es:ESHttpPost",
          "es:ESHttpPut",
        ]
        Resource = "${aws_opensearch_domain.this.arn}/*"
      }
    ]
  })

  tags = merge(
    {
      Environment = var.environment
      ManagedBy   = "terraform"
      Project     = "midas"
    },
    var.tags,
  )
}

resource "aws_iam_role_policy_attachment" "node_opensearch_write" {
  count      = var.eks_node_role_name != "" ? 1 : 0
  role       = var.eks_node_role_name
  policy_arn = aws_iam_policy.opensearch_write.arn
}

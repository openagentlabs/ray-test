variable "aws_account_id" {
  description = "AWS account ID used for remote state bucket"
  type        = string
}

variable "terraform_state_bucket" {
  description = "S3 bucket name for Terraform remote state"
  type        = string
}

# variable "tenant_id" {
#   description = "Tenant ID"
#   type        = string
# }

# variable "tenant_short_id" {
#   description = "Tenant short ID"
#   type        = string
# }

variable "environment" {
  description = "Tenant environment used by onboarding stack"
  type        = string
}

# variable "ecr_repository_url" {
#   description = "ECR repository URL for OMF image (without tag)"
#   type        = string
# }

# variable "image_tag" {
#   description = "Docker image tag to deploy"
#   type        = string
#   default     = "latest"
# }

variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "aws_provider_skip_credentials_validation" {
  description = <<-EOT
    When true, the AWS provider skips STS/metadata/account-id checks so terraform init/validate
    can run without live credentials (laptops, static analysis). Keep false (default) for any
    plan or apply against AWS. Jenkins must not set this to true.
  EOT
  type        = bool
  default     = false
}

variable "ec2_ssm_test_vpc_id" {
  description = "VPC ID for the SSM test EC2 instance. Default matches the MIDAS DEV us-east-1 workload VPC snapshot; set per environment in tfvars if your VPC differs."
  type        = string
  default     = "vpc-0c4d673f3e95a93eb"
}

variable "ec2_ssm_test_subnet_id" {
  description = "Optional private subnet ID for the SSM test instance. Empty uses SubnetGroup 1, then 2, then any subnet in the VPC."
  type        = string
  default     = ""
}

variable "ec2_ssm_test_clone_enabled" {
  description = <<-EOT
    When true, create a second Ubuntu SSM jumpbox identical to module ec2_ssm_test (same AMI, instance type, user_data/IAM pattern)
    but with a distinct name suffix (-clone). It is placed in the same subnet as the primary jumpbox so network placement matches
    the existing instance (e.g. i-0342e59b40cd01082). EKS access, EKS API SG rules, and NLB/ALB jumpbox HTTPS ingress are wired for the clone.
  EOT
  type        = bool
  default     = false
}

variable "ec2_ssm_test_clone_s3_bucket_names" {
  description = <<-EOT
    S3 bucket names the clone jumpbox instance role may access (ListBucket, GetBucketLocation, and object read/write/delete on arn:aws:s3:::name/*).
    Only applied when ec2_ssm_test_clone_enabled is true. The bucket's own bucket policy must still allow this role if the bucket enforces resource policies.
  EOT
  type        = list(string)
  default     = []
}

variable "ec2_ssm_windows_test_enabled" {
  description = "When true, create a private Windows Server 2022 EC2 instance with SSM (Session Manager from the AWS Console). Default false to avoid extra cost outside dev."
  type        = bool
  default     = false
}

variable "ec2_ssm_windows_test_subnet_id" {
  description = "Private subnet for the Windows SSM test instance. Empty uses the same subnet as module ec2_ssm_test (Ubuntu jumpbox) for identical network placement."
  type        = string
  default     = ""
}

variable "ec2_ssm_windows_test_instance_type" {
  description = "Instance type for the Windows SSM test VM (t3.large is a balanced default for light interactive testing)."
  type        = string
  default     = "t3.large"
}

variable "ec2_ssm_windows_test_root_volume_size_gb" {
  description = "Root gp3 volume size (GB) for the Windows test instance."
  type        = number
  default     = 50
}

variable "ec2_ssm_windows_test_key_pair_enabled" {
  description = <<-EOT
    When true (and ec2_ssm_windows_test_enabled), import the repo public key keypair/midas-windows-dev-local.pem.pub into AWS
    as EC2 key pair midas-<environment>-ec2-ssm-windows-test and set key_name on the Windows instance.
    Keep the matching private key keypair/midas-windows-dev-local.pem locally (gitignored); it is not in Terraform state.
  EOT
  type        = bool
  default     = false
}


variable "eks_vpc_id" {
  description = "VPC ID for the EKS cluster and node group. Default matches the MIDAS DEV us-east-1 snapshot; override per environment in tfvars."
  type        = string
  default     = "vpc-0c4d673f3e95a93eb"
}

variable "eks_cluster_subnet_ids" {
  description = "Subnets for EKS control plane and (by default) nodes; must span at least 2 AZs."
  type        = list(string)
  default = [
    "subnet-05c4fce53e16da9bc",
    "subnet-04d9f5b09b2dc9425",
  ]
}

variable "eks_cluster_name_prefix" {
  description = "EKS cluster name prefix; cluster name is {prefix}-{environment}. IAM deploy policy allows midas-eks-* role name patterns."
  type        = string
  default     = "midas-eks"
}

variable "eks_node_subnet_ids" {
  description = "Optional separate subnets for worker nodes; null uses eks_cluster_subnet_ids."
  type        = list(string)
  default     = null
  nullable    = true
}

variable "eks_node_instance_types" {
  description = "EC2 instance types for the EKS managed node group. Default m6i.4xlarge (16 vCPU, 64 GiB per instance). Helm pins the backend pod to 14600m CPU / 53Gi (Guaranteed QoS), leaving roughly 1.3+ cores and ~4.5Gi under typical EKS Allocatable for kube-system and node operations on the worker that runs the backend."
  type        = list(string)
  default     = ["m6i.4xlarge"]
}

variable "eks_node_desired_size" {
  description = "Desired worker count for the single managed node group. Default 2: one node effectively hosts the large backend pod; the other hosts frontend, graph, and cluster add-ons. Same instance type for every worker (eks_node_instance_types)."
  type        = number
  default     = 2
}

variable "eks_node_min_size" {
  description = "Minimum worker count (ASG floor). Default 2 matches the MIDAS two-node layout so the group cannot shrink to one worker without an explicit Terraform change."
  type        = number
  default     = 2
}

variable "eks_node_max_size" {
  description = "Maximum worker count for the managed node group."
  type        = number
  default     = 4
}

variable "rds_subnet_ids" {
  description = <<-EOT
    Optional list of private subnet IDs for the RDS DB subnet group. When null (default),
    falls back to the EKS node subnets (eks_node_subnet_ids or eks_cluster_subnet_ids).
    Set this explicitly to keep RDS pinned to the subnets where the live DB ENIs already
    exist when moving EKS workers to a different subnet pair (otherwise the subnet group
    update is rejected by AWS with InvalidParameterValue: subnet currently in use).
  EOT
  type        = list(string)
  default     = null
  nullable    = true
}

variable "elasticache_subnet_ids" {
  description = <<-EOT
    Optional list of private subnet IDs for the ElastiCache Redis subnet group. When null
    (default), falls back to the EKS node subnets (eks_node_subnet_ids or eks_cluster_subnet_ids).
    Set this explicitly to keep Redis pinned to the subnets where the live cache ENIs already
    exist when moving EKS workers to a different subnet pair (otherwise the subnet group
    update is rejected by AWS with SubnetInUse).
  EOT
  type        = list(string)
  default     = null
  nullable    = true
}

variable "eks_internal_alb_subnet_tag_enabled" {
  description = "When true, tag subnets with kubernetes.io/role/internal-elb=1 for internal ALBs (opt-in; coordinate if subnets are shared)."
  type        = bool
  default     = false
}

variable "eks_internal_alb_subnet_ids" {
  description = "Subnets to tag for internal ALBs; if empty and eks_internal_alb_subnet_tag_enabled is true, uses eks_node_subnet_ids or eks_cluster_subnet_ids."
  type        = list(string)
  default     = []
}

variable "eks_cluster_api_https_ingress_cidrs" {
  description = "CIDRs allowed TCP 443 to the EKS cluster security group (Kubernetes API). Override per environment in tfvars if needed."
  type        = list(string)
  default     = ["10.90.12.0/22"]
}

variable "eks_node_extra_secretsmanager_secret_arns" {
  description = "Extra Secrets Manager secret ARNs the EKS node role may read (GetSecretValue/DescribeSecret) for pods using the node credential chain-e.g. Bedrock/S3 slots when not inlined in midas-app-secret. RDS master and ElastiCache auth ARNs are added automatically when those modules are enabled."
  type        = list(string)
  default     = []
}

variable "rds_additional_ingress_cidrs_all_traffic" {
  description = "CIDRs allowed all-protocol ingress to the RDS PostgreSQL security group (e.g. cross-network DB clients). Empty adds no extra rules. Jenkins passes tfvars/midas-cross-network-db-access.tfvars; match or override for local plans."
  type        = list(string)
  default     = ["10.54.74.117/32", "10.54.67.114/32"]
}

variable "rds_additional_ingress_cidrs_tcp_5432" {
  description = "CIDRs allowed TCP 5432 only on the RDS security group (e.g. workload VPC CIDR for in-VPC VMs and pods). Empty adds no rules. Prefer this over widening rds_additional_ingress_cidrs_all_traffic for PostgreSQL-only access."
  type        = list(string)
  default     = []
}

variable "rds_additional_source_security_group_ids_tcp_5432" {
  description = "Extra security group IDs allowed TCP 5432 on the RDS security group (optional). Empty adds no rules."
  type        = list(string)
  default     = []
}

variable "elasticache_additional_ingress_cidrs_all_traffic" {
  description = "CIDRs allowed all-protocol ingress to the ElastiCache Redis security group (e.g. cross-network clients). Empty adds no extra rules. Jenkins passes tfvars/midas-cross-network-db-access.tfvars; match or override for local plans."
  type        = list(string)
  default     = ["10.54.74.117/32", "10.54.67.114/32"]
}

variable "rds_postgres_enabled" {
  description = "When true, create the dev-oriented PostgreSQL RDS module (same VPC/subnets as EKS nodes)."
  type        = bool
  default     = true
}

variable "rds_postgres_instance_class" {
  description = "RDS instance class for PostgreSQL (dev default: small burstable)."
  type        = string
  default     = "db.t4g.micro"
}

variable "rds_postgres_engine_version" {
  description = "PostgreSQL engine version string for aws_db_instance."
  type        = string
  default     = "15.17"
}

variable "rds_postgres_skip_final_snapshot" {
  description = "If true, skip final snapshot on destroy (typical for dev)."
  type        = bool
  default     = true
}

variable "rds_postgres_deletion_protection" {
  description = "When true, the instance cannot be deleted until this is disabled."
  type        = bool
  default     = false
}

variable "elasticache_redis_enabled" {
  description = "When true, create the ElastiCache Redis module (same VPC/subnets as EKS nodes)."
  type        = bool
  default     = true
}

variable "elasticache_redis_engine_version" {
  description = "Redis engine version for aws_elasticache_replication_group."
  type        = string
  default     = "7.1"
}

variable "elasticache_redis_node_type" {
  description = "ElastiCache node type (e.g. cache.t4g.micro)."
  type        = string
  default     = "cache.t4g.micro"
}

variable "elasticache_redis_num_cache_clusters" {
  description = "Number of cache nodes; 1 = single node, 2+ = primary + replicas with automatic failover."
  type        = number
  default     = 1
}

variable "secretsmanager_recovery_window_in_days" {
  description = "Secrets Manager deletion recovery window (7-30, or 0 for immediate delete). Default 7. The module ignores drift on this attribute after create so changing it does not replace the secret. Prefer 7+ in shared envs so ARNs stay stable."
  type        = number
  default     = 7

  validation {
    condition     = var.secretsmanager_recovery_window_in_days == 0 || (var.secretsmanager_recovery_window_in_days >= 7 && var.secretsmanager_recovery_window_in_days <= 30)
    error_message = "secretsmanager_recovery_window_in_days must be 0, or between 7 and 30."
  }
}

variable "secretsmanager_app_secret_seed_from_rds" {
  description = <<-EOT
    When true (default) and rds_postgres_enabled, Terraform creates aws_secretsmanager_secret_version for
    midas-{environment}-{region}/app with JSON string keys the Python Settings + secrets loader expect:
    AWS_RDS_POSTGRES_SECRET_ID (RDS master SM ARN), AWS_RDS_POSTGRES_DB_NAME,
    AWS_RDS_POSTGRES_HOST (RDS endpoint), AWS_RDS_POSTGRES_PORT ("5432"),
    AWS_SECRETS_MANAGER_REGION, AWS_REGION, AWS_DEFAULT_REGION, AWS_SECRETS_MANAGER_VERIFY_SSL.
    The host/port keys ensure pods can resolve the RDS endpoint even when the RDS-managed secret
    (after AWS rotation) contains only username/password. lifecycle.ignore_changes on secret_string
    keeps later populate-secrets.sh merges from being reverted. Set false when rds_postgres_enabled
    is false, or to skip the seed entirely.
  EOT
  type        = bool
  default     = true
  nullable    = false
  # Pairing with rds_postgres_enabled is enforced in checks-secretsmanager-rds.tf (check block).
}


# variable "task_cpu" {
#   description = "Task CPU units"
#   type        = string
#   default     = "512"
# }

# variable "task_memory_mb" {
#   description = "Task memory in MB"
#   type        = string
#   default     = "1024"
# }

# variable "desired_count" {
#   description = "Desired ECS task count"
#   type        = number
#   default     = 1
# }

# variable "omf_backend_secret_name" {
#   description = "Optional explicit secret name/ARN for OMF backend config; empty uses convention by tenant/env"
#   type        = string
#   default     = ""
# }

# variable "update_secret_values" {
#   description = "When true, Terraform updates the Secrets Manager secret JSON payload"
#   type        = bool
#   default     = false
# }

# variable "omf_backend_secret_values" {
#   description = "JSON key/value payload to store in the OMF backend secret"
#   type        = any
#   default = {
#     staging_s3_bucket               = "sagemaker-9f369070-p-cdz9lolfxp1a-data"
#     staging_account_id              = "639209084608"
#     staging_s3_base_dir             = "omf_cc_dep_base_dir"
#     staging_region                  = "us-east-1"
#     staging_access_role             = ""
#     transient_s3_bucket             = "sagemaker-9f369070-p-cdz9lolfxp1a-data"
#     transient_s3_base_dir           = "omf_cc_dep_transient_dir"
#     transient_region                = "us-east-1"
#     queue_s3_bucket                 = "sagemaker-9f369070-p-cdz9lolfxp1a-data"
#     queue_account_id                = "639209084608"
#     queue_s3_base_dir               = "omf_cc_dep_queue_dir"
#     queue_region                    = "us-east-1"
#     queue_access_role               = ""
#     use_regional_endpoints          = false
#     cognito_userinfo_url            = "https://sb-bti-userpool-domain.auth.us-east-1.amazoncognito.com/oauth2/userInfo"
#     cognito_token_url               = "https://sb-bti-userpool-domain.auth.us-east-1.amazoncognito.com/oauth2/token"
#     cognito_jwks_url                = ""
#     cognito_client_id               = "1m6rume6kfvk2clp6hgl5rl2hi"
#     cognito_client_secret           = "ao3tmlqbhvpg9413kjthgoj51vg66sf6g4dbupi3h9iaepnes"
#     cognito_request_timeout_seconds = 10
#     django_secret                   = "testSecret"
#     debug                           = true
#     allowed_hosts                   = ["*"]
#     cors_origin_allow_all           = false
#     cors_allow_credentials          = true
#     csrf_cookie_secure              = true
#     csrf_cookie_httponly            = true
#     session_cookie_secure           = true
#     secure_browser_xss_filter       = true
#     secure_ssl_redirect             = false
#     secure_hsts_seconds             = 31536000
#     secure_hsts_include_subdomains  = true
#     usecase_id                      = "OMFPRODCC"
#     response_timeout                = "300"
#     sqs_queue_name                  = "bticore-9f369070-standard-queue"
#     sqs_account_id                  = "639209084608"
#     sqs_region                      = "us-east-1"
#     backend_url                     = "postgresql://<user>:<password>@<host>.rds.amazonaws.com:5432/<db>"
#   }
# }

# variable "omf_backend_secret_reader_role_arns" {
#   description = "Additional IAM role ARNs allowed to read the OMF backend secret via resource policy."
#   type        = list(string)
#   default     = []
# }

# # Optional: when empty, default VPC and its first two subnets are used
# variable "vpc_id" {
#   description = "VPC ID for ECS/ALB. Leave empty to use default VPC"
#   type        = string
#   default     = ""
# }

# variable "vpc_cidr_block" {
#   description = "VPC CIDR block (e.g. 10.0.0.0/16) used for NLB->ECS security group ingress. Leave empty to fallback to 0.0.0.0/0."
#   type        = string
#   default     = ""
# }

# variable "private_subnet_a" {
#   description = "First private subnet ID for ECS/ALB. Leave empty to use default VPC subnets"
#   type        = string
#   default     = ""
# }

# variable "private_subnet_b" {
#   description = "Second private subnet ID for ECS/ALB. Leave empty to use default VPC subnets"
#   type        = string
#   default     = ""
# }

# variable "private_subnet_nlb_a" {
#   description = "First private subnet ID for OMF NLB. Leave empty to reuse private_subnet_a"
#   type        = string
#   default     = ""
# }

# variable "private_subnet_nlb_b" {
#   description = "Second private subnet ID for OMF NLB. Leave empty to reuse private_subnet_b"
#   type        = string
#   default     = ""
# }

# variable "ssl_certificate_arn" {
#   description = "Issued ACM certificate ARN in var.aws_region for ALB HTTPS (must include the environment-specific OMF hostname, for example omfanalytics-dev-exlerate.exlservice.com, or a matching SAN/wildcard). Empty = HTTP only on port 80."
#   type        = string
#   default     = ""
# }

# variable "omf_data_s3_manage_public_access_block" {
#   description = "When true, Terraform creates aws_s3_bucket_public_access_block for the OMF data and OpenSearch S3 buckets. Set false if an AWS Organizations SCP explicitly denies s3:PutBucketPublicAccessBlock for CI/deploy principals (IAM allows are ignored). Rely on account- or org-level S3 Block Public Access instead."
#   type        = bool
#   default     = false
# }

# variable "opensearch_kms_key_arn" {
#   description = "Optional KMS key ARN for OpenSearch Serverless collection encryption. Empty uses AWS-owned key."
#   type        = string
#   default     = ""
# }

# ---------------------------------------------------------------------------
# ALB + NLB ingress (private NLB in front of private ALB for EKS services)
# ---------------------------------------------------------------------------

variable "alb_nlb_enabled" {
  description = "When true, create the private NLB + ALB ingress module for EKS service exposure. Defaults to true — the NLB+ALB are deployed on every normal pipeline run. Set to false (or pass -var \"alb_nlb_enabled=false\") only to explicitly tear them down."
  type        = bool
  default     = true
}

variable "alb_nlb_certificate_arn" {
  description = "ARN of an ACM certificate in us-east-1 to attach to the ALB HTTPS:443 listener. Supports both ACM-issued and imported/self-signed certs. Leave empty to deploy NLB+ALB infrastructure without HTTPS listeners (safe before a cert is available)."
  type        = string
  default     = ""
}

variable "alb_nlb_public_https_hostname" {
  description = "When non-empty, the /frontend, /backend, and /graph path listener rules require a matching Host for this FQDN (and the internal ALB DNS) so they align with corporate DNS. Must be covered by the ACM cert. Empty omits host conditions (legacy behavior)."
  type        = string
  default     = ""
}

variable "backend_target_group_stickiness_seconds" {
  description = <<-EOT
    Cookie duration (seconds) for backend ALB target-group lb_cookie stickiness.
    Pins each browser session to one backend pod so the per-pod
    DataFrameStateManager singleton (backend/app/services/dataframe_state_manager.py)
    sees a coherent view. Required because MIDAS uses TargetGroupBinding
    (eks-tgb.tf) not Ingress, so the Service annotation on the Helm chart is
    ignored by the AWS LB Controller. Set 0 to disable stickiness. Default 86400 = 24h.
  EOT
  type        = number
  default     = 86400
}

variable "alb_subnet_ids" {
  description = "Subnets for the internal ALB (at least 2 AZs). Defaults to SubnetGroup 1 (largest /25 tier, both AZs) from the MIDAS DEV VPC snapshot."
  type        = list(string)
  default = [
    "subnet-05c4fce53e16da9bc",
    "subnet-04d9f5b09b2dc9425",
  ]
}

variable "nlb_subnet_ids" {
  description = "Subnets for the internal NLB (at least 2 AZs, one ENI per AZ = static private IP). Defaults to SubnetGroup 2 (/26 tier, both AZs) to isolate NLB IPs from EKS node scaling."
  type        = list(string)
  default = [
    "subnet-0bc74e29f773eb7a4",
    "subnet-04f6c506a5098aa40",
  ]
}

variable "nlb_corporate_ingress_cidrs" {
  description = "CIDRs allowed TCP 443 ingress to the NLB security group (corporate / TGW-attached networks). Defaults to the Jenkins/EKS API CIDR plus known cross-network ranges."
  type        = list(string)
  default     = ["10.90.12.0/22", "10.54.74.117/32", "10.54.67.114/32", "10.54.5.10/32"]
}

variable "eks_ci_automation_principal_arn" {
  description = "IAM principal ARN for CI/automation (e.g. midas-deployer-role) to receive EKS API access via access entries. Empty skips creating CI access entry."
  type        = string
  default     = ""
}

variable "terraform_sync_app_secret_to_kubernetes" {
  description = <<-EOT
    When true (default), Terraform reads the live midas-{environment}-us-east-1/app SecretString and applies
    kubernetes_secret_v1 midas-app-secret in namespace midas-apps (namespace must already exist; Jenkins ensures midas-apps before terraform plan).
    Requires the terraform apply host to reach the private EKS API and valid AWS credentials for aws eks get-token
    (set eks_ci_automation_principal_arn for the deployer role). Set false when apply runs without cluster network
    path; Jenkins helm-deploy-releases.sh will continue to sync SM to K8s instead.
  EOT
  type        = bool
  default     = true
  nullable    = false
}

variable "midas_test_secret_001_value" {
  description = "The value for the test secret"
  type        = string
  default     = "hello from keith"
}

# ---------------------------------------------------------------------------
# Frontend Secrets Manager — Cognito + VITE_BASE_URL
# Passed to module.secretsmanager_frontend and seeded into
# midas-{environment}-{region}/frontend on first apply.
# All VITE_* values are non-sensitive: they are baked into the public JS bundle
# by Vite at Docker build time.  lifecycle.ignore_changes on the secret version
# ensures Terraform never reverts post-deploy updates.
# ---------------------------------------------------------------------------

variable "frontend_vite_cognito_domain" {
  type        = string
  description = "Cognito Hosted UI domain (https://, no trailing slash). Example: https://exldecision-ai.auth.us-east-1.amazoncognito.com"

  validation {
    condition     = startswith(var.frontend_vite_cognito_domain, "https://") && !endswith(var.frontend_vite_cognito_domain, "/")
    error_message = "frontend_vite_cognito_domain must start with https:// and must not have a trailing slash."
  }
}

variable "frontend_vite_cognito_client_id" {
  type        = string
  description = "Cognito app-client ID for the deployed environment (NOT the local/dev client). Validated to be lowercase alphanumeric."

  validation {
    condition     = can(regex("^[a-z0-9]+$", var.frontend_vite_cognito_client_id))
    error_message = "frontend_vite_cognito_client_id must be a lowercase alphanumeric Cognito client ID."
  }
}

variable "frontend_vite_cognito_redirect_uri" {
  type        = string
  description = "OAuth callback URL registered on the Cognito app client. Must end with /auth/callback."

  validation {
    condition     = endswith(var.frontend_vite_cognito_redirect_uri, "/auth/callback")
    error_message = "frontend_vite_cognito_redirect_uri must end with /auth/callback."
  }
}

variable "frontend_vite_cognito_logout_redirect_uri" {
  type        = string
  description = "Post-logout redirect URL registered on the Cognito app client (https://)."

  validation {
    condition     = startswith(var.frontend_vite_cognito_logout_redirect_uri, "https://")
    error_message = "frontend_vite_cognito_logout_redirect_uri must start with https://."
  }
}

variable "frontend_vite_cognito_scopes" {
  type        = string
  description = "Space-separated OAuth scopes. Must match the Cognito app client allowed scopes."
  default     = "openid email profile"
}

variable "frontend_vite_base_url" {
  type        = string
  description = "Public HTTPS base URL of the deployed app (no trailing slash). Used by React to reach the FastAPI backend. Example: https://exldecision-ai-dev.exlservice.com"

  validation {
    condition     = startswith(var.frontend_vite_base_url, "https://") && !endswith(var.frontend_vite_base_url, "/")
    error_message = "frontend_vite_base_url must start with https:// and must not have a trailing slash."
  }
}

# ---------------------------------------------------------------------------
# Observability
# ---------------------------------------------------------------------------

variable "observability_log_retention_days" {
  description = "Retention in days for the backend application CloudWatch Log Group (/midas/<environment>/backend)."
  type        = number
  default     = 30
}

variable "observability_kms_key_arn" {
  description = "Optional KMS CMK ARN to encrypt the backend application CloudWatch Log Group. Leave empty to use the AWS-managed default."
  type        = string
  default     = ""
}

variable "observability_amp_enabled" {
  description = "When true, deploy the Amazon Managed Prometheus (AMP) workspace and attach the Remote Write IAM policy to the EKS node role. Set false (default) until the ADOT Collector DaemonSet is deployed. See docs/adr/0001-midas-amp-amg-observability.md."
  type        = bool
  default     = false
}

variable "observability_opensearch_enabled" {
  description = "When true, deploy the Amazon OpenSearch Service domain for KQL log search and attach the write IAM policy to the EKS node role. Set false (default) until Fluent Bit dual-write is configured. See docs/adr/0002-midas-kql-log-search.md."
  type        = bool
  default     = false
}

variable "observability_fluent_bit_enabled" {
  description = "When true, deploy the aws-for-fluent-bit DaemonSet to ship container stdout logs from midas-apps namespace to CloudWatch Logs at /midas/<environment>/backend (Phase A log shipping). Requires the Fluent Bit image to be mirrored to the private ECR repo first — see deploy/ecs-app/modules/observability-fluent-bit/main.tf."
  type        = bool
  default     = false
}

variable "observability_cloudwatch_agent_enabled" {
  description = "When true, deploy the amazon-cloudwatch-observability Helm release (CloudWatch Agent DaemonSet + operator) so EKS node, pod, and container metrics (incl. node_memory_*, pod_memory_utilization) appear in CloudWatch under namespace ContainerInsights. Non-disruptive: only adds DaemonSet pods to existing nodes; does not roll the managed node group. Requires the cloudwatch-agent and cloudwatch-agent-operator images to be mirrored to private ECR first — see deploy/scripts/ci/mirror-addon-images-ecr.sh and deploy/ecs-app/modules/observability-cloudwatch-agent/main.tf."
  type        = bool
  default     = false
}

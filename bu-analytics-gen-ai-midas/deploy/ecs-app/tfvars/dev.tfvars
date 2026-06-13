# MIDAS EKS app - dev
# Use: terraform plan -var-file=tfvars/dev.tfvars

aws_account_id         = "811391286931"
terraform_state_bucket = "midas-dev-us-east-1-terraform-811391286931"
environment            = "dev"
aws_region             = "us-east-1"

# EKS workers: 2× identical instances in one managed node group (default m6i.4xlarge =
# 16 vCPU, 64 GiB per node per AWS spec). Backend Helm runs 2 replicas at
# 14600m CPU / 53Gi requests+limits, so target one backend pod per worker.
# Typical Allocatable (~15890m CPU, ~58.5Gi) still leaves kube-system DaemonSet
# headroom on each node (VPC CNI, kube-proxy, Fluent Bit, EBS CSI, ADOT when enabled).
eks_node_instance_types = ["m6i.4xlarge"]
eks_node_desired_size = 2
eks_node_min_size     = 2
eks_node_max_size     = 6

# Use all four MIDAS DEV worker-eligible subnets. Adding the /25 pair gives the
# ASG enough IP capacity to launch new instances even though the /26 pair is
# currently saturated. Networking is identical across all 4 (same route table,
# same TGW egress, same VPC endpoints). RDS/Redis stay pinned via the dedicated
# rds_subnet_ids / elasticache_subnet_ids overrides below.
eks_node_subnet_ids = [
  "subnet-05c4fce53e16da9bc",
  "subnet-04d9f5b09b2dc9425",
  "subnet-0bc74e29f773eb7a4",
  "subnet-04f6c506a5098aa40",
]

# Pin RDS and ElastiCache subnet groups to the existing data-tier subnets
# (10.72.134.0/25 + 10.72.134.128/25) where the live DB and Redis ENIs already exist.
# Without this, Terraform would try to swap the subnet groups to follow
# eks_node_subnet_ids and AWS would reject the change with SubnetInUse /
# InvalidParameterValue (subnets currently in use). RDS/Redis stay where they were
# created — only EKS workers move to subnets with free IP capacity.
rds_subnet_ids = [
  "subnet-05c4fce53e16da9bc",
  "subnet-04d9f5b09b2dc9425",
]
elasticache_subnet_ids = [
  "subnet-05c4fce53e16da9bc",
  "subnet-04d9f5b09b2dc9425",
]

# NLB + ALB ingress for EKS. Set to false only to explicitly tear them down.
alb_nlb_enabled = true

# ACM certificate ARN for the ALB HTTPS:443 listener (same cert as AI Gateway C1
# request: arn:aws:acm:us-east-1:811391286931:certificate/9242f7d2-b91c-4517-9548-28936fdf8cf6).
# Certificate must reach ISSUED before apply; PENDING may fail listener creation.
# The cert must include the public hostname below (e.g. SAN) for SNI in browsers.
alb_nlb_certificate_arn = "arn:aws:acm:us-east-1:811391286931:certificate/9242f7d2-b91c-4517-9548-28936fdf8cf6"

# Corporate CNAME for NLB/ALB path rules (Host header on /frontend, /backend, /graph).
alb_nlb_public_https_hostname = "exldecision-ai-dev.exlservice.com"

# ---------------------------------------------------------------------------
# Frontend Secrets Manager — Cognito + VITE_BASE_URL (midas-dev-us-east-1/frontend)
# Cognito user pool : us-east-1_5JL0dpXwK  (ins-midas-dev-user-pool)
# App client        : 1j436t8d6g8ggklvtcti73s141  (Exldecisionai-Dev)
#                     n35e8smlbvo6cv4tv4bjsvj6v is the Local client — do NOT use here.
# Callback URL registered on the app client: /auth/callback
# Logout URL registered on the app client  : /logout
# ---------------------------------------------------------------------------
frontend_vite_cognito_domain              = "https://exldecision-ai.auth.us-east-1.amazoncognito.com"
frontend_vite_cognito_client_id           = "1j436t8d6g8ggklvtcti73s141"
frontend_vite_cognito_redirect_uri        = "https://exldecision-ai-dev.exlservice.com/auth/callback"
frontend_vite_cognito_logout_redirect_uri = "https://exldecision-ai-dev.exlservice.com/logout"
frontend_vite_cognito_scopes              = "openid email profile"
frontend_vite_base_url                    = "https://exldecision-ai-dev.exlservice.com"

# ---------------------------------------------------------------------------
# Observability (Phase A — CloudWatch log group always created above)
# Phase B — Amazon Managed Prometheus (AMP). Set to true when ADOT Collector
# DaemonSet is ready to deploy. See docs/adr/0001-midas-amp-amg-observability.md
# ---------------------------------------------------------------------------
observability_amp_enabled = true
# Phase A — Fluent Bit DaemonSet ships midas-apps stdout to /midas/dev/backend.
# Requires aws-for-fluent-bit image mirrored to private ECR before first apply.
# See deploy/ecs-app/modules/observability-fluent-bit/main.tf for mirror command.
observability_fluent_bit_enabled = true

# CloudWatch Container Insights — CloudWatch Agent DaemonSet + operator.
# Emits node, pod, and container metrics (incl. RAM) to CloudWatch namespace
# ContainerInsights. Visible in CloudWatch -> Insights -> Container Insights.
# Non-disruptive: only adds DaemonSet pods to existing midas-eks-dev nodes.
# Requires cloudwatch-agent and cloudwatch-agent-operator images mirrored to
# private ECR before first apply — see deploy/scripts/ci/mirror-addon-images-ecr.sh.
observability_cloudwatch_agent_enabled = true

# Second Ubuntu SSM jumpbox (same spec/subnet as primary); enable in dev for parity with i-0342e59b40cd01082-style access.
ec2_ssm_test_clone_enabled         = true
ec2_ssm_test_clone_s3_bucket_names = ["keith-bucket-test-001"]

# Private Windows Server 2022 + SSM Session Manager (same VPC / EKS worker subnet pool as EKS).
ec2_ssm_windows_test_enabled = true
# Generate RSA key, register in EC2, write PEM to repo keypair/ (gitignored); attach to Windows instance.
ec2_ssm_windows_test_key_pair_enabled = true

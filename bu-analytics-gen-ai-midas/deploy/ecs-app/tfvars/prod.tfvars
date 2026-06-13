# MIDAS EKS app - prod
# Use: terraform plan -var-file=tfvars/prod.tfvars

aws_account_id         = "811391286931"
terraform_state_bucket = "midas-prod-us-east-1-terraform-811391286931"
environment            = "prod"
aws_region             = "us-east-1"

# EKS: two workers, same type (16 vCPU / 64 GiB per m6i.4xlarge); see dev.tfvars for sizing rationale.
eks_node_instance_types = ["m6i.4xlarge"]
eks_node_desired_size   = 4
eks_node_min_size       = 4
eks_node_max_size       = 6

# NLB + ALB ingress for EKS. Set to false only to explicitly tear them down.
alb_nlb_enabled = true

ec2_ssm_windows_test_enabled = false

# ACM certificate domain for the ALB HTTPS:443 listener.
# Terraform auto-discovers the ARN from ACM — no manual ARN lookup required.
# The certificate must be ISSUED in us-east-1 before terraform apply runs.
# Update this value when the prod certificate domain is confirmed.
alb_nlb_certificate_arn = "" # Set to the ACM certificate ARN once imported for prod

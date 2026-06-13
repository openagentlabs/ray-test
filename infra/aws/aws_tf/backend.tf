# Backend auth uses profile ``kt-acc`` (synced from infra/envs/dev/.env.aws).
terraform {
  backend "s3" {
    bucket       = "arb-ai-assistant-terraform-state"
    key          = "infra/aws_tf/terraform.tfstate"
    region       = "us-east-1"
    encrypt      = true
    profile      = "kt-acc"
    use_lockfile = true
  }
}

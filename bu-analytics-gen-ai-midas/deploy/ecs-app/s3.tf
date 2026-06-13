# -----------------------------------------------------------------------------
# Register Terraform modules from deploy/ecs-app/modules/ in this file (or main.tf).
# The Jenkins pipeline applies the ecs-app root; any module block here is included.
# -----------------------------------------------------------------------------

module "s3" {
  source = "./modules/s3"

  aws_account_id = var.aws_account_id
  environment    = var.environment
  aws_region     = var.aws_region
}

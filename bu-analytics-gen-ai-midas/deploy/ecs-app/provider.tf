provider "aws" {
  region = var.aws_region

  # When var.aws_provider_skip_credentials_validation is true (e.g. TF_VAR_...=true for local CI),
  # init/validate can run without STS; must stay false for real plan/apply.
  skip_credentials_validation = var.aws_provider_skip_credentials_validation
  skip_metadata_api_check     = var.aws_provider_skip_credentials_validation
  skip_requesting_account_id  = var.aws_provider_skip_credentials_validation
}

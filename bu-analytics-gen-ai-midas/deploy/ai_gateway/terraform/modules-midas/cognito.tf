module "cognito" {
  # checkov:skip=CKV_TF_1: The UC-DevOps corporate Terraform module catalogue uses semantic version tags (v0.0.7) as the supported pinning mechanism. Commit-SHA pinning is not part of the upstream team's release process; switching would create maintenance drift across all consumer projects.
  source                                = "git::https://ucgithub.exlservice.com/Unified-Cloud-DevOps/uc-iac-aws-tf-cognito.git//.?ref=v0.0.7"
  alias_attributes                      = ["email", "phone_number", "preferred_username", ]
  auto_verified_attributes              = ["email", ]
  cognito_user_pool_name                = var.cognito_upn
  deletion_protection                   = "ACTIVE"
  mfa_configuration                     = "OPTIONAL"
  mfa_configuration_enable              = true
  account_recovery_setting_name         = "verified_email"
  account_recovery_setting_priority     = 1
  attr_require_verification             = ["email", ]
  username_configuration_case_sensitive = false
  verification_default_email_option     = "CONFIRM_WITH_CODE"
  password_policy = {
    "default" = {
      minimum_length                   = 8
      require_lowercase                = true
      require_numbers                  = true
      require_symbols                  = true
      require_uppercase                = true
      temporary_password_validity_days = 7
    }
  }

  # Custom attributes referenced by SAML attribute mapping (console: custom:groups, custom:oid, custom:tenant_id).
  user_attribute_schema = {
    "groups" = {
      attribute_data_type      = "String"
      developer_only_attribute = false
      mutable                  = true
      required                 = false

      string_attribute_constraints = {
        max_length = "2048"
        min_length = "0"
      }
    }
    "oid" = {
      attribute_data_type      = "String"
      developer_only_attribute = false
      mutable                  = true
      required                 = false

      string_attribute_constraints = {
        max_length = "2048"
        min_length = "0"
      }
    }
    "tenant_id" = {
      attribute_data_type      = "String"
      developer_only_attribute = false
      mutable                  = true
      required                 = false

      string_attribute_constraints = {
        max_length = "2048"
        min_length = "0"
      }
    }
  }

  user_groups = {}

  cognito_users = {}

  # Do not use timestamp() in tags — it changes every plan and forces perpetual user pool updates.
  # Default tags from the AWS provider still apply via tags_all.

  #Domain configuration for pool
  domain_enable = true
  domain        = "${var.cognito_domain}-${var.environment}"


  # identity_providers — match console IdP "EXLerateAI" (Azure AD / Entra SAML claim URIs).
  # MIDAS in-tree fork: gated behind var.enable_saml_identity_provider. On a fresh deploy
  # the cognito-sso-credentials secret holds "PopulateMe" → invalid SAML XML → IdP creation
  # fails. Flip the variable AND populate the secret with real Entra federation metadata XML
  # (M-13) before re-applying.
  enable_identity_providers = var.enable_saml_identity_provider
  identity_providers = var.enable_saml_identity_provider ? [
    {
      provider_name = "EXLerateAI"
      provider_type = "SAML"
      provider_details = {
        MetadataFile = local.saml_metadata
      }
      # Fortify "Insecure Transport": false positive.
      # The strings below are SAML 2.0 claim-type namespace identifiers defined by
      # Microsoft / OASIS (IANA-registered, opaque URI keys). They are not HTTP
      # transport endpoints — AWS Cognito requires them verbatim. Cannot be changed.
      # Accepted risk per ADR 0010.
      attribute_mapping = {
        "custom:groups"    = "http://schemas.microsoft.com/ws/2008/06/identity/claims/groups"
        "custom:oid"       = "http://schemas.microsoft.com/identity/claims/objectidentifier"
        "custom:tenant_id" = "http://schemas.microsoft.com/identity/claims/tenantid"
        "email"            = "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress"
        "name"             = "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/displayname"
        "username"         = "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/nameidentifier"
      }
    },
  ] : []

  # app_clients set to false to avoid creating clients in the module
  # the module doesnt support multiple client creations
  client_enable = false
  clients       = {}

}

# App Client definitions below 
resource "aws_cognito_user_pool_client" "exlerate_ai_gateway_client" {
  access_token_validity                         = 60
  allowed_oauth_flows                           = ["code", ]
  allowed_oauth_flows_user_pool_client          = true
  allowed_oauth_scopes                          = ["email", "openid", "phone", "profile", ]
  auth_session_validity                         = 3
  callback_urls                                 = ["https://${var.cognito_domain}-${var.environment}.exlservice.com/callback"]
  enable_propagate_additional_user_context_data = false
  enable_token_revocation                       = true
  explicit_auth_flows                           = ["ALLOW_REFRESH_TOKEN_AUTH", "ALLOW_USER_SRP_AUTH"]
  id_token_validity                             = 60
  logout_urls                                   = []
  name                                          = "EXLERATE-AI-GATEWAY-${var.environment}-CLIENT"
  generate_secret                               = true
  prevent_user_existence_errors                 = "ENABLED"
  read_attributes                               = ["address", "birthdate", "custom:groups", "custom:oid", "custom:tenant_id", "email", "email_verified", "family_name", "gender", "given_name", "locale", "middle_name", "name", "nickname", "phone_number", "phone_number_verified", "picture", "preferred_username", "profile", "updated_at", "website", "zoneinfo", ]
  refresh_token_validity                        = 30
  supported_identity_providers                  = var.enable_saml_identity_provider ? ["COGNITO", "EXLerateAI"] : ["COGNITO"]
  write_attributes                              = ["address", "birthdate", "custom:groups", "custom:oid", "custom:tenant_id", "email", "family_name", "gender", "given_name", "locale", "middle_name", "name", "nickname", "phone_number", "picture", "preferred_username", "profile", "updated_at", "website", "zoneinfo", ]
  token_validity_units {
    access_token  = "minutes"
    id_token      = "minutes"
    refresh_token = "days"
  }
  user_pool_id = module.cognito.user_pool_id
  depends_on = [
    module.cognito.identity_provider,
    module.cognito.resource_server
  ]
}

resource "aws_cognito_user_pool_client" "langfuse_observability_client" {
  access_token_validity                         = 60
  allowed_oauth_flows                           = ["code", ]
  allowed_oauth_flows_user_pool_client          = true
  allowed_oauth_scopes                          = ["email", "openid", "phone", "profile", ]
  auth_session_validity                         = 3
  callback_urls                                 = ["https://exldecision-ai-dev-aigw-langfuse.exlservice.com/api/auth/callback/custom"]
  enable_propagate_additional_user_context_data = false
  enable_token_revocation                       = true
  explicit_auth_flows                           = ["ALLOW_USER_AUTH", "ALLOW_USER_SRP_AUTH", "ALLOW_REFRESH_TOKEN_AUTH"]
  id_token_validity                             = 60
  logout_urls                                   = ["https://exldecision-ai-dev-aigw-langfuse.exlservice.com"]
  name                                          = "langfuse-observability-${var.environment}"
  generate_secret                               = true
  prevent_user_existence_errors                 = "ENABLED"
  read_attributes                               = ["address", "birthdate", "custom:groups", "custom:oid", "custom:tenant_id", "email", "email_verified", "family_name", "gender", "given_name", "locale", "middle_name", "name", "nickname", "phone_number", "phone_number_verified", "picture", "preferred_username", "profile", "updated_at", "website", "zoneinfo", ]
  refresh_token_validity                        = 30
  supported_identity_providers                  = var.enable_saml_identity_provider ? ["COGNITO", "EXLerateAI"] : ["COGNITO"]
  write_attributes                              = ["address", "birthdate", "custom:groups", "custom:oid", "custom:tenant_id", "email", "family_name", "gender", "given_name", "locale", "middle_name", "name", "nickname", "phone_number", "picture", "preferred_username", "profile", "updated_at", "website", "zoneinfo", ]
  user_pool_id                                  = module.cognito.user_pool_id
  token_validity_units {
    access_token  = "minutes"
    id_token      = "minutes"
    refresh_token = "days"
  }

  depends_on = [
    module.cognito.identity_provider,
    module.cognito.resource_server
  ]
}

resource "aws_cognito_user_pool_client" "exlerate_langfuse_public_client" {
  access_token_validity                         = 60
  allowed_oauth_flows                           = ["code", ]
  allowed_oauth_flows_user_pool_client          = true
  allowed_oauth_scopes                          = ["email", "openid", "phone", "profile", ]
  auth_session_validity                         = 3
  callback_urls                                 = ["https://exlerate-ai-observability-${var.environment}.exlservice.com"]
  enable_propagate_additional_user_context_data = false
  enable_token_revocation                       = true
  explicit_auth_flows                           = ["ALLOW_USER_AUTH", "ALLOW_USER_SRP_AUTH", "ALLOW_REFRESH_TOKEN_AUTH"]
  id_token_validity                             = 60
  logout_urls                                   = []
  name                                          = "exlerate-${var.environment}-langfuse-public-client"
  generate_secret                               = true
  prevent_user_existence_errors                 = "ENABLED"
  read_attributes                               = ["address", "birthdate", "custom:groups", "custom:oid", "custom:tenant_id", "email", "email_verified", "family_name", "gender", "given_name", "locale", "middle_name", "name", "nickname", "phone_number", "phone_number_verified", "picture", "preferred_username", "profile", "updated_at", "website", "zoneinfo", ]
  refresh_token_validity                        = 30
  supported_identity_providers                  = var.enable_saml_identity_provider ? ["EXLerateAI"] : ["COGNITO"]
  write_attributes                              = ["address", "birthdate", "custom:groups", "custom:oid", "custom:tenant_id", "email", "family_name", "gender", "given_name", "locale", "middle_name", "name", "nickname", "phone_number", "picture", "preferred_username", "profile", "updated_at", "website", "zoneinfo", ]
  token_validity_units {
    access_token  = "minutes"
    id_token      = "minutes"
    refresh_token = "days"
  }
  user_pool_id = module.cognito.user_pool_id

  depends_on = [
    module.cognito.identity_provider,
    module.cognito.resource_server
  ]
}

resource "aws_cognito_user_pool_client" "exlerate_pacs_app_client" {
  access_token_validity                         = 60
  allowed_oauth_flows                           = ["code", ]
  allowed_oauth_flows_user_pool_client          = true
  allowed_oauth_scopes                          = ["email", "openid", "phone", "profile", ]
  auth_session_validity                         = 3
  callback_urls                                 = ["https://exlerate-ui-${var.environment}.exlservice.com/"]
  enable_propagate_additional_user_context_data = false
  enable_token_revocation                       = true
  explicit_auth_flows                           = ["ALLOW_USER_AUTH", "ALLOW_CUSTOM_AUTH", "ALLOW_REFRESH_TOKEN_AUTH"]
  id_token_validity                             = 60
  logout_urls                                   = []
  name                                          = "exlerate-${var.environment}-pacs-app-client"
  generate_secret                               = true
  prevent_user_existence_errors                 = "ENABLED"
  read_attributes                               = ["address", "birthdate", "custom:groups", "custom:oid", "custom:tenant_id", "email", "email_verified", "family_name", "gender", "given_name", "locale", "middle_name", "name", "nickname", "phone_number", "phone_number_verified", "picture", "preferred_username", "profile", "updated_at", "website", "zoneinfo", ]
  refresh_token_validity                        = 30
  supported_identity_providers                  = var.enable_saml_identity_provider ? ["EXLerateAI"] : ["COGNITO"]
  write_attributes                              = ["address", "birthdate", "custom:groups", "custom:oid", "custom:tenant_id", "email", "family_name", "gender", "given_name", "locale", "middle_name", "name", "nickname", "phone_number", "picture", "preferred_username", "profile", "updated_at", "website", "zoneinfo", ]
  token_validity_units {
    access_token  = "minutes"
    id_token      = "minutes"
    refresh_token = "days"
  }
  user_pool_id = module.cognito.user_pool_id


  depends_on = [
    module.cognito.identity_provider,
    module.cognito.resource_server
  ]
}

resource "aws_cognito_user_pool_client" "exlerate_langfuse_server" {
  access_token_validity                         = 60
  allowed_oauth_flows                           = ["code", ]
  allowed_oauth_flows_user_pool_client          = true
  allowed_oauth_scopes                          = ["email", "openid", "phone", "profile", ]
  auth_session_validity                         = 3
  callback_urls                                 = ["https://exlerate-ai-observability-${var.environment}.exlservice.com/api/auth/callback/custom"]
  enable_propagate_additional_user_context_data = false
  enable_token_revocation                       = true
  explicit_auth_flows                           = ["ALLOW_USER_AUTH", "ALLOW_USER_SRP_AUTH", "ALLOW_REFRESH_TOKEN_AUTH"]
  id_token_validity                             = 60
  logout_urls                                   = []
  name                                          = "exlerate-${var.environment}-langfuse-server"
  generate_secret                               = true
  prevent_user_existence_errors                 = "ENABLED"
  read_attributes                               = ["address", "birthdate", "custom:groups", "custom:oid", "custom:tenant_id", "email", "email_verified", "family_name", "gender", "given_name", "locale", "middle_name", "name", "nickname", "phone_number", "phone_number_verified", "picture", "preferred_username", "profile", "updated_at", "website", "zoneinfo", ]
  refresh_token_validity                        = 30
  supported_identity_providers                  = var.enable_saml_identity_provider ? ["EXLerateAI"] : ["COGNITO"]
  write_attributes                              = ["address", "birthdate", "custom:groups", "custom:oid", "custom:tenant_id", "email", "family_name", "gender", "given_name", "locale", "middle_name", "name", "nickname", "phone_number", "picture", "preferred_username", "profile", "updated_at", "website", "zoneinfo", ]
  token_validity_units {
    access_token  = "minutes"
    id_token      = "minutes"
    refresh_token = "days"
  }
  user_pool_id = module.cognito.user_pool_id


  depends_on = [
    module.cognito.identity_provider,
    module.cognito.resource_server
  ]
}
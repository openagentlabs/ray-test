#################################
#     Cognito SSO Credentials
#################################
resource "aws_secretsmanager_secret" "cognito_sso_credentials" {
  name                    = "cognito-sso-credentials-${var.eks_cluster_name}"
  recovery_window_in_days = 7
}

# Cognito SAML metadata
resource "aws_secretsmanager_secret_version" "cognito_sso_credentials" {
  secret_id = aws_secretsmanager_secret.cognito_sso_credentials.id

  secret_string = jsonencode({
    "metadata" = "PopulateMe"
  })

  lifecycle {
    ignore_changes = [secret_string]
  }
}

data "aws_secretsmanager_secret_version" "cognito_sso_credentials" {
  secret_id  = aws_secretsmanager_secret.cognito_sso_credentials.id
  depends_on = [aws_secretsmanager_secret_version.cognito_sso_credentials]
}

#################################
#     JFrog Credentials
#################################
# Need to define the credentials once in dev/UAT, then from there we reference the secret in other environments.


# Secret Def
resource "aws_secretsmanager_secret" "jfrog_regcred" {
  count                   = var.environment == "dev" || var.environment == "uat" ? 1 : 0
  name                    = "jfrog-regcred"
  recovery_window_in_days = 7
}

resource "aws_secretsmanager_secret_version" "jfrog_regcred" {
  count     = var.environment == "dev" || var.environment == "uat" ? 1 : 0
  secret_id = aws_secretsmanager_secret.jfrog_regcred[count.index].id
  secret_string = jsonencode({
    "username" = "PopulateMe"
    "password" = "PopulateMe"
    "email"    = "PopulateMe"
    "server"   = "PopulateMe"
  })
  lifecycle {
    ignore_changes = [secret_string]
  }
}

# Reference to the same secret in other environments.
data "aws_secretsmanager_secret_version" "jfrog_regcred" {
  count      = var.environment == "dev" || var.environment == "uat" ? 1 : 0
  secret_id  = aws_secretsmanager_secret.jfrog_regcred[count.index].id
  depends_on = [aws_secretsmanager_secret_version.jfrog_regcred]
}

data "aws_secretsmanager_secret" "jfrog_regcred_import" {
  count = var.environment == "qa" || var.environment == "dev-stable" ? 1 : 0
  arn   = var.jfrog_regcred_arn
}
data "aws_secretsmanager_secret_version" "jfrog_regcred_import" {
  count     = var.environment == "qa" || var.environment == "dev-stable" ? 1 : 0
  secret_id = data.aws_secretsmanager_secret.jfrog_regcred_import[count.index].id
}

#################################
#     LiteLLM
#################################

# Random DB passwords
resource "random_password" "pg_db_password" {
  length  = 16
  special = false
}

# Stack DB secret
resource "random_password" "stack_secret" {
  length  = 16
  special = false
}

# LiteLLM Master Key secret
resource "random_password" "litellm_master_key_secret" {
  length  = 21
  special = false
}

# LiteLLM Salt Key secret
resource "random_password" "litellm_salt_key_secret" {
  length  = 21
  special = false
}

resource "aws_secretsmanager_secret" "pg_db_password_secret" {
  name_prefix             = "pg-db-password-${var.eks_cluster_name}"
  recovery_window_in_days = 7
}

resource "aws_secretsmanager_secret_version" "pg_db_password_value" {
  secret_id     = aws_secretsmanager_secret.pg_db_password_secret.id
  secret_string = random_password.pg_db_password.result
  lifecycle {
    ignore_changes = [secret_string]
  }
}

#################################
resource "aws_secretsmanager_secret" "litellm_master_key" {
  name                    = "litellm-master-key-${var.eks_cluster_name}"
  recovery_window_in_days = 7
}

resource "aws_secretsmanager_secret_version" "litellm_master_key" {
  secret_id     = aws_secretsmanager_secret.litellm_master_key.id
  secret_string = random_password.litellm_master_key_secret.result
  lifecycle {
    ignore_changes = [secret_string]
  }
}

data "aws_secretsmanager_secret_version" "litellm_master_key" {
  secret_id  = aws_secretsmanager_secret.litellm_master_key.id
  depends_on = [aws_secretsmanager_secret_version.litellm_master_key]
}
#################################
resource "aws_secretsmanager_secret" "litellm_salt_key" {
  name                    = "litellm-salt-key-${var.eks_cluster_name}"
  recovery_window_in_days = 7
}

resource "aws_secretsmanager_secret_version" "litellm_salt_key" {
  secret_id     = aws_secretsmanager_secret.litellm_salt_key.id
  secret_string = random_password.litellm_salt_key_secret.result
  lifecycle {
    ignore_changes = [secret_string]
  }
}

data "aws_secretsmanager_secret_version" "litellm_salt_key" {
  secret_id  = aws_secretsmanager_secret.litellm_salt_key.id
  depends_on = [aws_secretsmanager_secret_version.litellm_salt_key]
}
##################################
resource "aws_secretsmanager_secret" "litellm_stack" {
  name                    = "litellm-stack-db-secret-${var.eks_cluster_name}"
  recovery_window_in_days = 7
}

resource "aws_secretsmanager_secret_version" "litellm_stack" {
  secret_id = aws_secretsmanager_secret.litellm_stack.id
  secret_string = jsonencode({
    "username" = var.lite_db_username
    "password" = random_password.stack_secret.result
  })
  lifecycle {
    ignore_changes = [secret_string]
  }
}

data "aws_secretsmanager_secret_version" "litellm_stack" {
  secret_id  = aws_secretsmanager_secret.litellm_stack.id
  depends_on = [aws_secretsmanager_secret_version.litellm_stack]
}
##################################
resource "aws_secretsmanager_secret" "litellm_license" {
  name                    = "litellm-license-${var.eks_cluster_name}"
  recovery_window_in_days = 7
}

# LiteLLM license: NO version written (same reason as langfuse_ee_license_key above).
# AWS Secrets Manager rejects empty SecretString. The K8s secret consumed by the LiteLLM
# Helm release receives a HARDCODED "" via `local.litellm_secret_vals.litellm-license`
# in litellm_app_deps.tf. Empty env var = community/OSS mode per docs.litellm.ai.
# Operator overrides post-license-purchase via `aws secretsmanager put-secret-value`
# + re-introducing the data source. Bare secret kept here so the operator has a target.
##################################
resource "aws_secretsmanager_secret" "langfuse_public_key" {
  name                    = "langfuse-public-key-${var.eks_cluster_name}"
  recovery_window_in_days = 7
}

resource "aws_secretsmanager_secret_version" "langfuse_public_key" {
  secret_id     = aws_secretsmanager_secret.langfuse_public_key.id
  secret_string = "PopulateMe"
  lifecycle {
    ignore_changes = [secret_string]
  }
}

data "aws_secretsmanager_secret_version" "langfuse_public_key" {
  secret_id  = aws_secretsmanager_secret.langfuse_public_key.id
  depends_on = [aws_secretsmanager_secret_version.langfuse_public_key]
}
##################################
resource "aws_secretsmanager_secret" "LANGFUSE_SECRET_KEY" {
  name                    = "langfuse-secret-key-${var.eks_cluster_name}"
  recovery_window_in_days = 7
}

resource "aws_secretsmanager_secret_version" "LANGFUSE_SECRET_KEY" {
  secret_id     = aws_secretsmanager_secret.LANGFUSE_SECRET_KEY.id
  secret_string = "PopulateMe"
  lifecycle {
    ignore_changes = [secret_string]
  }
}

data "aws_secretsmanager_secret_version" "LANGFUSE_SECRET_KEY" {
  secret_id  = aws_secretsmanager_secret.LANGFUSE_SECRET_KEY.id
  depends_on = [aws_secretsmanager_secret_version.LANGFUSE_SECRET_KEY]
}
##################################

resource "aws_secretsmanager_secret" "LANGFUSE_HOST" {
  name                    = "langfuse-host-${var.eks_cluster_name}"
  recovery_window_in_days = 7
}

resource "aws_secretsmanager_secret_version" "LANGFUSE_HOST" {
  secret_id     = aws_secretsmanager_secret.LANGFUSE_HOST.id
  secret_string = "PopulateMe"
  lifecycle {
    ignore_changes = [secret_string]
  }
}

data "aws_secretsmanager_secret_version" "LANGFUSE_HOST" {
  secret_id  = aws_secretsmanager_secret.LANGFUSE_HOST.id
  depends_on = [aws_secretsmanager_secret_version.LANGFUSE_HOST]
}
##################################

resource "aws_secretsmanager_secret" "AZURE_OPENAI_API_KEY" {
  name                    = "azure-openai-api-key-${var.eks_cluster_name}"
  recovery_window_in_days = 7
}

resource "aws_secretsmanager_secret_version" "AZURE_OPENAI_API_KEY" {
  secret_id     = aws_secretsmanager_secret.AZURE_OPENAI_API_KEY.id
  secret_string = "PopulateMe"
  lifecycle {
    ignore_changes = [secret_string]
  }
}

data "aws_secretsmanager_secret_version" "AZURE_OPENAI_API_KEY" {
  secret_id  = aws_secretsmanager_secret.AZURE_OPENAI_API_KEY.id
  depends_on = [aws_secretsmanager_secret_version.AZURE_OPENAI_API_KEY]
}
##################################

resource "aws_secretsmanager_secret" "AZURE_OPENAI_API_KEY_EASTUS2" {
  name                    = "azure-openai-api-key-use2-${var.eks_cluster_name}"
  recovery_window_in_days = 7
}

resource "aws_secretsmanager_secret_version" "AZURE_OPENAI_API_KEY_EASTUS2" {
  secret_id     = aws_secretsmanager_secret.AZURE_OPENAI_API_KEY_EASTUS2.id
  secret_string = "PopulateMe"
  lifecycle {
    ignore_changes = [secret_string]
  }
}

data "aws_secretsmanager_secret_version" "AZURE_OPENAI_API_KEY_EASTUS2" {
  secret_id  = aws_secretsmanager_secret.AZURE_OPENAI_API_KEY_EASTUS2.id
  depends_on = [aws_secretsmanager_secret_version.AZURE_OPENAI_API_KEY_EASTUS2]
}
##################################

resource "aws_secretsmanager_secret" "VERTEXAI_CREDENTIALS_JSON" {
  name                    = "vertexai-credentials-json-${var.eks_cluster_name}"
  recovery_window_in_days = 7
}

resource "aws_secretsmanager_secret_version" "VERTEXAI_CREDENTIALS_JSON_REF" {
  secret_id = aws_secretsmanager_secret.VERTEXAI_CREDENTIALS_JSON.id
  secret_string = jsonencode({
    "type"                        = "service_account",
    "project_id"                  = "PopulateMe",
    "private_key_id"              = "PopulateMe",
    "private_key"                 = "PopulateMe",
    "client_email"                = "PopulateMe",
    "client_id"                   = "PopulateMe",
    "auth_uri"                    = "PopulateMe",
    "token_uri"                   = "PopulateMe",
    "auth_provider_x509_cert_url" = "PopulateMe",
    "client_x509_cert_url"        = "PopulateMe",
    "universe_domain"             = "googleapis.com",
  })

  lifecycle {
    ignore_changes = [secret_string]
  }
}

data "aws_secretsmanager_secret_version" "VERTEXAI_CREDENTIALS_JSON_REF" {
  secret_id  = aws_secretsmanager_secret.VERTEXAI_CREDENTIALS_JSON.id
  depends_on = [aws_secretsmanager_secret_version.VERTEXAI_CREDENTIALS_JSON_REF]
}

################################
#    Langfuse
################################

# Langfuse Enterprise Edition license key (OSS-MODE: NO VERSION WRITTEN).
#
# DESIGN (MIDAS): the application MUST receive `LANGFUSE_EE_LICENSE_KEY=""` to run in
# MIT-licensed OSS mode. AWS Secrets Manager REJECTS empty SecretString values
# (`InvalidRequestException: You must provide either SecretString or SecretBinary`),
# so we cannot store "" in the AWS secret directly. Instead:
#   - We create the bare AWS secret (no version) so the operator has a place to PUT a
#     real license value once SOP M-7 (Langfuse EE purchase) lands. AWS allows secrets
#     with zero versions; only `data.aws_secretsmanager_secret_version` would fail to
#     read them, so we DELIBERATELY do NOT have a `data` source here.
#   - The K8s secret consumed by the Langfuse Helm release receives a HARDCODED ""
#     value (see langfuse_app_deps.tf, `local.langfuse_secret_vals.langfuse-ee-license`).
#     This bypasses AWS entirely for the OSS-mode default and lets the pod start.
#
# Promotion path (post-M-7):
#   1) `populate-secrets.sh --ee-license-value '<real>' --force` writes the real license
#      to this AWS secret.
#   2) Re-introduce the `data` source + flip `langfuse_secret_vals.langfuse-ee-license`
#      to read from it.
#   3) `terragrunt apply` to roll the K8s secret + helm release.
resource "aws_secretsmanager_secret" "langfuse_ee_license_key" {
  name                           = "${var.eks_cluster_name}-langfuse-ee-license"
  force_overwrite_replica_secret = true
}

##################################

# Langfuse Cognito SSO credentials.
# MIDAS in-tree fork: upstream relied on out-of-band population of these two secrets.
# We populate them in-Terraform from the langfuse_observability_client outputs so the
# downstream `data.aws_secretsmanager_secret_version` lookups always find a current
# version (was failing on a fresh deploy).
resource "aws_secretsmanager_secret" "langfuse_cognito_client_id" {
  name                           = "langfuse-cognito-client-id-${var.eks_cluster_name}"
  force_overwrite_replica_secret = true
}

resource "aws_secretsmanager_secret_version" "langfuse_cognito_client_id" {
  secret_id     = aws_secretsmanager_secret.langfuse_cognito_client_id.id
  secret_string = aws_cognito_user_pool_client.langfuse_observability_client.id
  lifecycle {
    ignore_changes = [secret_string]
  }
}

data "aws_secretsmanager_secret_version" "langfuse_cognito_client_id" {
  secret_id  = aws_secretsmanager_secret.langfuse_cognito_client_id.id
  depends_on = [aws_secretsmanager_secret_version.langfuse_cognito_client_id]
}

###################################
resource "aws_secretsmanager_secret" "langfuse_cognito_client_secret" {
  name                           = "langfuse-cognito-client-secret-${var.eks_cluster_name}"
  force_overwrite_replica_secret = true
}

resource "aws_secretsmanager_secret_version" "langfuse_cognito_client_secret" {
  secret_id     = aws_secretsmanager_secret.langfuse_cognito_client_secret.id
  secret_string = aws_cognito_user_pool_client.langfuse_observability_client.client_secret
  lifecycle {
    ignore_changes = [secret_string]
  }
}

data "aws_secretsmanager_secret_version" "langfuse_cognito_client_secret" {
  secret_id  = aws_secretsmanager_secret.langfuse_cognito_client_secret.id
  depends_on = [aws_secretsmanager_secret_version.langfuse_cognito_client_secret]
}

###################################

# Random DB passwords langfuse
resource "random_password" "pg_db_password_langfuse" {
  length  = 16
  special = false
}

resource "aws_secretsmanager_secret" "langfuse_pg_db_password_secret" {
  name_prefix             = "langfuse-pg-db-password-${var.environment}"
  recovery_window_in_days = 7
}

resource "aws_secretsmanager_secret_version" "langfuse_pg_db_password_value" {
  secret_id     = aws_secretsmanager_secret.langfuse_pg_db_password_secret.id
  secret_string = random_password.pg_db_password_langfuse.result
  lifecycle {
    ignore_changes = [secret_string]
  }
}

##################################

resource "aws_secretsmanager_secret" "langfuse_next_autg_password" {
  name                    = "langfuse_nxtauth_password-${var.eks_cluster_name}"
  recovery_window_in_days = 7
}

resource "aws_secretsmanager_secret_version" "langfuse_next_autg_password" {
  secret_id = aws_secretsmanager_secret.langfuse_next_autg_password.id
  secret_string = jsonencode({
    "nextauth-secret" = "PopulateMe"
  })

  lifecycle {
    ignore_changes = [secret_string]
  }
}

data "aws_secretsmanager_secret_version" "langfuse_next_autg_password" {
  secret_id  = aws_secretsmanager_secret.langfuse_next_autg_password.id
  depends_on = [aws_secretsmanager_secret_version.langfuse_next_autg_password]
}

################################
#     Clickhouse
################################

# Random password for clickhouse and langfuse to share
resource "random_password" "ch_admin_password" {
  length  = 32
  special = false
}

resource "random_password" "ch_langfuse_password" {
  length  = 32
  special = false
}

resource "aws_secretsmanager_secret" "ch_admin_password" {
  name                    = "ch_admin_password-${var.eks_cluster_name}"
  recovery_window_in_days = 7
}

resource "aws_secretsmanager_secret_version" "ch_admin_password" {
  secret_id     = aws_secretsmanager_secret.ch_admin_password.id
  secret_string = random_password.ch_admin_password.result
  lifecycle {
    ignore_changes = [secret_string]
  }
}

resource "aws_secretsmanager_secret" "ch_langfuse_password" {
  name                    = "ch_langfuse_password-${var.eks_cluster_name}"
  recovery_window_in_days = 7
}

resource "aws_secretsmanager_secret_version" "ch_langfuse_password" {
  secret_id     = aws_secretsmanager_secret.ch_langfuse_password.id
  secret_string = random_password.ch_langfuse_password.result
  lifecycle {
    ignore_changes = [secret_string]
  }
}

################################
#    C1 API
################################
# Random password for c1 api
resource "random_password" "pg_db_password_c1_api" {
  length  = 16
  special = false
}

resource "aws_secretsmanager_secret" "c1_api_pg_db_password_secret" {
  name_prefix             = "c1-api-pg-db-password-${var.environment}"
  recovery_window_in_days = 7
}

resource "aws_secretsmanager_secret_version" "c1_api_pg_db_password_value" {
  secret_id     = aws_secretsmanager_secret.c1_api_pg_db_password_secret.id
  secret_string = random_password.pg_db_password_c1_api.result
  lifecycle {
    ignore_changes = [secret_string]
  }
}

##################################
resource "aws_secretsmanager_secret" "langfuse_org_public_key" {
  name_prefix             = "langfuse_org_public_key_${var.environment}"
  recovery_window_in_days = 7
}

resource "aws_secretsmanager_secret_version" "langfuse_org_public_key_value" {
  secret_id     = aws_secretsmanager_secret.langfuse_org_public_key.id
  secret_string = "PopulateMe"
  lifecycle {
    ignore_changes = [secret_string]
  }
}

data "aws_secretsmanager_secret_version" "langfuse_org_public_key_value" {
  secret_id  = aws_secretsmanager_secret.langfuse_org_public_key.id
  depends_on = [aws_secretsmanager_secret_version.langfuse_org_public_key_value]
}

##################################

resource "aws_secretsmanager_secret" "langfuse_org_secret_key" {
  name_prefix             = "langfuse_org_secret_key_${var.environment}"
  recovery_window_in_days = 7
}

resource "aws_secretsmanager_secret_version" "langfuse_org_secret_key_value" {
  secret_id     = aws_secretsmanager_secret.langfuse_org_secret_key.id
  secret_string = "PopulateMe"
  lifecycle {
    ignore_changes = [secret_string]
  }
}

data "aws_secretsmanager_secret_version" "langfuse_org_secret_key_value" {
  secret_id  = aws_secretsmanager_secret.langfuse_org_secret_key.id
  depends_on = [aws_secretsmanager_secret_version.langfuse_org_secret_key_value]
}
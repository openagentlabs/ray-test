variable "aws_account_id" {
  type        = string
  description = "AWS account ID (passed from the ecs-app root module)."
}

variable "environment" {
  type        = string
  description = "Tenant environment (e.g. dev, uat, prod) - matches Jenkins TENANT_ENV."
}

variable "aws_region" {
  type        = string
  description = "AWS region."
  default     = "us-east-1"
}

variable "recovery_window_in_days" {
  type        = number
  description = "0 = immediate delete (name reusable right away); otherwise AWS requires 7-30 for scheduled deletion."
  default     = 7

  validation {
    condition     = var.recovery_window_in_days == 0 || (var.recovery_window_in_days >= 7 && var.recovery_window_in_days <= 30)
    error_message = "recovery_window_in_days must be 0, or between 7 and 30."
  }
}

# ---------------------------------------------------------------------------
# Frontend Cognito + base-URL configuration.
# These values are baked into the JS bundle by Vite at Docker build time.
# They are NOT secrets — they are safe to store here (all VITE_* vars are
# already embedded in the public JS bundle in production).
# lifecycle.ignore_changes on secret_string (in main.tf) ensures Terraform
# never reverts manual or CI updates once the secret has been seeded.
# ---------------------------------------------------------------------------

variable "vite_cognito_domain" {
  type        = string
  description = "Cognito Hosted UI domain (https://). Example: https://exldecision-ai.auth.us-east-1.amazoncognito.com"

  validation {
    condition     = startswith(var.vite_cognito_domain, "https://") && !endswith(var.vite_cognito_domain, "/")
    error_message = "vite_cognito_domain must start with https:// and must not have a trailing slash."
  }
}

variable "vite_cognito_client_id" {
  type        = string
  description = "Cognito app-client ID for the deployed environment (NOT the local/dev client)."

  validation {
    condition     = can(regex("^[a-z0-9]+$", var.vite_cognito_client_id))
    error_message = "vite_cognito_client_id must be a lowercase alphanumeric Cognito client ID."
  }
}

variable "vite_cognito_redirect_uri" {
  type        = string
  description = "OAuth callback URL registered on the Cognito app client. Must end with /auth/callback."

  validation {
    condition     = endswith(var.vite_cognito_redirect_uri, "/auth/callback")
    error_message = "vite_cognito_redirect_uri must end with /auth/callback."
  }
}

variable "vite_cognito_logout_redirect_uri" {
  type        = string
  description = "Post-logout redirect URL registered on the Cognito app client."

  validation {
    condition     = startswith(var.vite_cognito_logout_redirect_uri, "https://")
    error_message = "vite_cognito_logout_redirect_uri must start with https://."
  }
}

variable "vite_cognito_scopes" {
  type        = string
  description = "Space-separated OAuth scopes. Defaults match the Cognito app client allowed scopes."
  default     = "openid email profile"
}

variable "vite_base_url" {
  type        = string
  description = "Public HTTPS base URL of the deployed app (no trailing slash). Used by the React app to reach the FastAPI backend. Example: https://exldecision-ai-dev.exlservice.com"

  validation {
    condition     = startswith(var.vite_base_url, "https://") && !endswith(var.vite_base_url, "/")
    error_message = "vite_base_url must start with https:// and must not have a trailing slash."
  }
}

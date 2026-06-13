"""
Cognito Hosted UI + Entra ID federation integration.

See plan: cognito-entra-auth-integration-v2.1-6bdea7.md
"""

from app.services.cognito.settings import CognitoSettings, get_cognito_settings

__all__ = ["CognitoSettings", "get_cognito_settings"]

"""AWS Secrets Manager integration: typed bundles for RDS, S3, ElastiCache, Bedrock."""

from app.core.secrets.contracts import ISecretsReader
from app.core.secrets.deps import ApplicationSecrets, get_application_secrets
from app.core.secrets.loader import load_application_secrets_bundle
from app.core.secrets.models import (
    ApplicationSecretsBundle,
    BedrockSecrets,
    ElastiCacheSecrets,
    RDSPostgresSecrets,
    S3Secrets,
)
from app.core.secrets.slot_definitions import SECRET_SLOTS, SecretSlotDefinition

__all__ = [
    "ISecretsReader",
    "SECRET_SLOTS",
    "SecretSlotDefinition",
    "load_application_secrets_bundle",
    "get_application_secrets",
    "ApplicationSecrets",
    "ApplicationSecretsBundle",
    "RDSPostgresSecrets",
    "S3Secrets",
    "ElastiCacheSecrets",
    "BedrockSecrets",
]

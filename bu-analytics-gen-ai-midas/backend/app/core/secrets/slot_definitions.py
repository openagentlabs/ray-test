"""
Declarative registry: which `.env` keys map to which bundle field and parser.

Add a new AWS-backed integration by appending a ``SecretSlotDefinition`` to ``SECRET_SLOTS``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable, Dict, Final, Optional, Tuple

from app.core.secrets.models import (
    BedrockSecrets,
    ElastiCacheSecrets,
    RDSPostgresSecrets,
    S3Secrets,
)

if TYPE_CHECKING:
    from app.core.config import Settings

SecretIdFn = Callable[["Settings"], Optional[str]]
InlineJsonFn = Callable[["Settings"], Optional[str]]
ParserFn = Callable[[Dict[str, Any]], Any]


@dataclass(frozen=True)
class SecretSlotDefinition:
    """One logical secret (identifier from env → Secrets Manager or inline JSON → typed model)."""

    bundle_attr: str
    """Field name on ``ApplicationSecretsBundle`` (e.g. ``rds_postgres``)."""
    label: str
    """Log label for errors and warnings."""
    secret_id_from_settings: SecretIdFn
    """Returns ``AWS_*_SECRET_ID`` (or equivalent) from settings."""
    inline_json_from_settings: InlineJsonFn
    """Returns optional ``AWS_*_SECRET_JSON`` override."""
    parse: ParserFn
    """Maps SecretString JSON object to a frozen/dataclass secret type."""


def _elasticache_secret_id(settings: "Settings") -> Optional[str]:
    v = (settings.AWS_ELASTICACHE_SECRET_ID or "").strip()
    return v or None


SECRET_SLOTS: Final[Tuple[SecretSlotDefinition, ...]] = (
    SecretSlotDefinition(
        bundle_attr="rds_postgres",
        label="rds_postgres",
        secret_id_from_settings=lambda s: s.AWS_RDS_POSTGRES_SECRET_ID,
        inline_json_from_settings=lambda s: s.AWS_RDS_POSTGRES_SECRET_JSON,
        parse=RDSPostgresSecrets.from_mapping,
    ),
    SecretSlotDefinition(
        bundle_attr="s3",
        label="s3",
        secret_id_from_settings=lambda s: s.AWS_S3_SECRET_ID,
        inline_json_from_settings=lambda s: s.AWS_S3_SECRET_JSON,
        parse=S3Secrets.from_mapping,
    ),
    SecretSlotDefinition(
        bundle_attr="elasticache",
        label="elasticache",
        secret_id_from_settings=_elasticache_secret_id,
        inline_json_from_settings=lambda s: s.AWS_ELASTICACHE_SECRET_JSON,
        parse=ElastiCacheSecrets.from_mapping,
    ),
    SecretSlotDefinition(
        bundle_attr="bedrock",
        label="bedrock",
        secret_id_from_settings=lambda s: s.AWS_BEDROCK_SECRET_ID,
        inline_json_from_settings=lambda s: s.AWS_BEDROCK_SECRET_JSON,
        parse=BedrockSecrets.from_mapping,
    ),
)

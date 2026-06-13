"""
Chain of responsibility for resolving Redis URL: ElastiCache (Secrets Manager) → explicit URL → REDIS_URL.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

from botocore.exceptions import ClientError

from app.core.boto_session import build_boto3_session
from app.core.redis_secret_format import build_redis_url_from_secret_dict
from app.core.session.contracts import IRedisUrlProvider

logger = logging.getLogger(__name__)

_build_url_from_secret_dict = build_redis_url_from_secret_dict


class AwsSecretsManagerRedisUrlProvider(IRedisUrlProvider):
    """Resolve Redis URL from AWS Secrets Manager (ElastiCache credentials)."""

    def __init__(
        self,
        secret_id: Optional[str],
        region: Optional[str],
        *,
        verify_ssl: bool = True,
        profile_name: Optional[str] = None,
    ) -> None:
        self._secret_id = (secret_id or "").strip() or None
        self._region = (region or "").strip() or None
        self._verify_ssl = verify_ssl
        self._profile_name = (profile_name or "").strip() or None

    def get_redis_url(self) -> Optional[str]:
        if not self._secret_id:
            return None

        try:
            if not self._verify_ssl:
                logger.warning(
                    "Secrets Manager client SSL verification is disabled (AWS_SECRETS_MANAGER_VERIFY_SSL=false). "
                    "Use only for local/dev if TLS fails."
                )
            if self._profile_name:
                logger.info("Secrets Manager: using AWS profile %r (set AWS_PROFILE in .env)", self._profile_name)
            try:
                session = build_boto3_session(self._profile_name)
            except ImportError:
                logger.error("boto3 is required when a session secret ARN/id is set in configuration")
                return None
            client_kwargs: Dict[str, Any] = {"verify": self._verify_ssl}
            if self._region:
                client_kwargs["region_name"] = self._region
            client = session.client("secretsmanager", **client_kwargs)
            resp = client.get_secret_value(SecretId=self._secret_id)
            raw = resp.get("SecretString") or ""
            if not raw:
                logger.warning("Secrets Manager returned empty SecretString for %s", self._secret_id)
                return None
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                payload = {"redis_url": raw.strip()}

            if not isinstance(payload, dict):
                return None
            url = _build_url_from_secret_dict(payload)
            if url:
                logger.info("Resolved Redis URL from AWS Secrets Manager for session store")
            return url
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "")
            if code == "ExpiredTokenException":
                logger.warning(
                    "AWS credentials are expired; cannot call Secrets Manager for the session Redis URL. "
                    "Refresh credentials (e.g. `aws sso login` or new temporary keys), then restart. "
                    "Until then the app falls back to SESSION_REDIS_URL, REDIS_URL, or in-memory sessions."
                )
                return None
            logger.exception("Secrets Manager error (%s): %s", code, exc)
            return None
        except Exception as exc:
            logger.exception("Failed to load Redis URL from Secrets Manager: %s", exc)
            return None


class ExplicitSessionRedisUrlProvider(IRedisUrlProvider):
    """SESSION_REDIS_URL when set."""

    def __init__(self, url: Optional[str]) -> None:
        self._url = (url or "").strip() or None

    def get_redis_url(self) -> Optional[str]:
        return self._url


class FallbackSharedRedisUrlProvider(IRedisUrlProvider):
    """Shared REDIS_URL from app settings (same variable as other Redis consumers)."""

    def __init__(self, url: Optional[str]) -> None:
        self._url = (url or "").strip() or None

    def get_redis_url(self) -> Optional[str]:
        return self._url


class RedisUrlResolutionChain:
    """Ordered chain: ElastiCache/Secrets Manager → SESSION_REDIS_URL → REDIS_URL."""

    def __init__(self, providers: list[IRedisUrlProvider]) -> None:
        self._providers = providers

    def resolve(self) -> Optional[str]:
        for provider in self._providers:
            url = provider.get_redis_url()
            if url:
                return url
        return None


def build_default_redis_url_chain() -> RedisUrlResolutionChain:
    """Construct the chain from ``app.core.config.settings`` (values from ``backend/.env``)."""
    from app.core.config import settings as app_settings

    s = app_settings
    secret_id = s.SESSION_ELASTICACHE_SECRET_ARN or s.SESSION_REDIS_SECRET_ID
    region = s.SESSION_AWS_REGION or s.AWS_REGION or s.AWS_DEFAULT_REGION

    providers: list[IRedisUrlProvider] = [
        AwsSecretsManagerRedisUrlProvider(
            secret_id=secret_id,
            region=region,
            verify_ssl=s.AWS_SECRETS_MANAGER_VERIFY_SSL,
            profile_name=s.AWS_PROFILE,
        ),
        ExplicitSessionRedisUrlProvider(s.SESSION_REDIS_URL),
        FallbackSharedRedisUrlProvider(s.REDIS_URL),
    ]
    return RedisUrlResolutionChain(providers)

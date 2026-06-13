"""AWS Secrets Manager implementation of ISecretsReader."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

from botocore.exceptions import ClientError

from app.core.boto_session import build_boto3_session
from app.core.secrets.contracts import ISecretsReader

logger = logging.getLogger(__name__)


class AwsSecretsManagerReader(ISecretsReader):
    """Fetches secrets via boto3 ``secretsmanager.get_secret_value``."""

    def __init__(
        self,
        region: Optional[str],
        *,
        verify_ssl: bool = True,
        profile_name: Optional[str] = None,
    ) -> None:
        self._region = (region or "").strip() or None
        self._verify_ssl = verify_ssl
        self._profile_name = (profile_name or "").strip() or None

    def get_secret_json(self, secret_id: str) -> Dict[str, Any]:
        sid = (secret_id or "").strip()
        if not sid:
            raise ValueError("secret_id is empty")

        try:
            if self._profile_name:
                logger.info("Secrets Manager: using AWS profile %r", self._profile_name)
            try:
                session = build_boto3_session(self._profile_name)
            except ImportError as exc:
                raise RuntimeError("boto3 is required for AWS Secrets Manager") from exc
            client_kwargs: Dict[str, Any] = {"verify": self._verify_ssl}
            if self._region:
                client_kwargs["region_name"] = self._region
            client = session.client("secretsmanager", **client_kwargs)
            resp = client.get_secret_value(SecretId=sid)
            raw = resp.get("SecretString") or ""
            if not raw:
                raise ValueError(f"Secrets Manager returned empty SecretString for {sid!r}")
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Secret {sid!r} is not valid JSON") from exc
            if not isinstance(parsed, dict):
                raise ValueError(f"Secret {sid!r} JSON root must be an object")
            return parsed
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "")
            logger.exception("Secrets Manager error (%s) for %s", code, sid)
            raise

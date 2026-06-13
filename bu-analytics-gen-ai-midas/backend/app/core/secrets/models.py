"""Typed views of AWS Secrets Manager payloads for RDS, S3, ElastiCache, and Bedrock."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Dict, Optional
from urllib.parse import quote_plus

from app.core.redis_secret_format import build_redis_url_from_secret_dict


def _str_field(data: Dict[str, Any], *keys: str, default: str = "") -> str:
    for k in keys:
        v = data.get(k)
        if v is not None and str(v).strip():
            return str(v).strip()
    return default


def rds_database_field_absent(data: Dict[str, Any]) -> bool:
    """True if RDS secret JSON has no usable database name key (merge dbname from config before parse)."""
    return not _str_field(data, "dbname", "database", "db", "DB_NAME")


def _int_field(data: Dict[str, Any], key: str, default: int) -> int:
    v = data.get(key)
    if v is None:
        return default
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True)
class RDSPostgresSecrets:
    username: str
    password: str
    host: str
    port: int
    database: str

    @classmethod
    def from_mapping(cls, data: Dict[str, Any]) -> RDSPostgresSecrets:
        username = _str_field(data, "username", "user", "USER_NAME")
        password = _str_field(data, "password", "passwd")
        host = _str_field(data, "host", "hostname", "endpoint", "address")
        port = _int_field(data, "port", 5432)
        database = _str_field(data, "dbname", "database", "db", "DB_NAME")
        if not all((username, password, host, database)):
            raise ValueError(
                "RDS/Postgres secret must include username, password, host, and dbname/database"
            )
        return cls(
            username=username,
            password=password,
            host=host,
            port=port,
            database=database,
        )

    def sqlalchemy_url(
        self,
        driver: str = "postgresql+psycopg2",
        sslmode: Optional[str] = None,
    ) -> str:
        """Sync-style SQLAlchemy URL; quote user/password for special characters."""
        user_q = quote_plus(self.username)
        pass_q = quote_plus(self.password)
        base = f"{driver}://{user_q}:{pass_q}@{self.host}:{self.port}/{self.database}"
        sm = (sslmode or "").strip()
        if sm:
            base = f"{base}?sslmode={quote_plus(sm)}"
        return base


@dataclass(frozen=True)
class S3Secrets:
    # Access keys are optional: when absent, the default boto3 credentials chain
    # is used (IRSA / EC2 instance profile / node role). This is the preferred
    # path on EKS where the node role already has an S3 inline policy.
    access_key_id: Optional[str]
    secret_access_key: Optional[str]
    session_token: Optional[str]
    region: Optional[str]
    bucket: Optional[str]

    @classmethod
    def from_mapping(cls, data: Dict[str, Any]) -> S3Secrets:
        access_key = _str_field(
            data,
            "access_key_id",
            "AWS_ACCESS_KEY_ID",
            "aws_access_key_id",
            "accessKeyId",
        ) or None
        secret_key = _str_field(
            data,
            "secret_access_key",
            "AWS_SECRET_ACCESS_KEY",
            "aws_secret_access_key",
            "secretAccessKey",
        ) or None
        token_raw = _str_field(data, "session_token", "AWS_SESSION_TOKEN", "aws_session_token")
        region_raw = _str_field(data, "region", "AWS_REGION", "aws_region")
        bucket_raw = _str_field(data, "bucket", "bucket_name", "S3_BUCKET", "S3_BUCKET_NAME")
        if not bucket_raw and not (access_key and secret_key):
            raise ValueError(
                "S3 secret must include at least a bucket name "
                "(or access_key_id + secret_access_key for a legacy keyed secret)"
            )
        token = token_raw or None
        region = region_raw or None
        bucket = bucket_raw or None
        return cls(
            access_key_id=access_key,
            secret_access_key=secret_key,
            session_token=token,
            region=region,
            bucket=bucket,
        )

    def apply_to_environ(self) -> None:
        """Set ``AWS_*`` for boto3 S3 client construction (optional region)."""
        if self.access_key_id:
            os.environ["AWS_ACCESS_KEY_ID"] = self.access_key_id
        if self.secret_access_key:
            os.environ["AWS_SECRET_ACCESS_KEY"] = self.secret_access_key
        if self.session_token:
            os.environ["AWS_SESSION_TOKEN"] = self.session_token
        if self.region:
            os.environ["AWS_REGION"] = self.region
            os.environ["AWS_DEFAULT_REGION"] = self.region


@dataclass(frozen=True)
class ElastiCacheSecrets:
    """ElastiCache / Redis credentials as returned from Secrets Manager."""

    _payload: Dict[str, Any]

    @classmethod
    def from_mapping(cls, data: Dict[str, Any]) -> ElastiCacheSecrets:
        if not isinstance(data, dict):
            raise ValueError("ElastiCache secret must be a JSON object")
        return cls(_payload=dict(data))

    def as_redis_url(self) -> Optional[str]:
        return build_redis_url_from_secret_dict(self._payload)

    @property
    def raw(self) -> Dict[str, Any]:
        return self._payload


@dataclass(frozen=True)
class BedrockSecrets:
    """Credentials and optional region for Amazon Bedrock (LiteLLM / boto3)."""

    region: Optional[str]
    access_key_id: Optional[str]
    secret_access_key: Optional[str]
    session_token: Optional[str]

    @classmethod
    def from_mapping(cls, data: Dict[str, Any]) -> BedrockSecrets:
        region = _str_field(data, "region", "AWS_REGION", "aws_region") or None
        access_key = _str_field(
            data,
            "access_key_id",
            "AWS_ACCESS_KEY_ID",
            "aws_access_key_id",
        ) or None
        secret_key = _str_field(
            data,
            "secret_access_key",
            "AWS_SECRET_ACCESS_KEY",
            "aws_secret_access_key",
        ) or None
        token = _str_field(data, "session_token", "AWS_SESSION_TOKEN", "aws_session_token") or None
        return cls(
            region=region,
            access_key_id=access_key,
            secret_access_key=secret_key,
            session_token=token,
        )

    def apply_to_environ(self) -> None:
        """Set ``AWS_*`` environment variables for boto3 / LiteLLM (skips unset fields)."""
        if self.region:
            os.environ["AWS_REGION"] = self.region
            os.environ["AWS_DEFAULT_REGION"] = self.region
            os.environ["AWS_REGION_NAME"] = self.region
        if self.access_key_id:
            os.environ["AWS_ACCESS_KEY_ID"] = self.access_key_id
        if self.secret_access_key:
            os.environ["AWS_SECRET_ACCESS_KEY"] = self.secret_access_key
        if self.session_token:
            os.environ["AWS_SESSION_TOKEN"] = self.session_token


@dataclass
class ApplicationSecretsBundle:
    """Resolved secrets for application AWS integrations (None = not configured or failed optional load)."""

    rds_postgres: Optional[RDSPostgresSecrets] = None
    s3: Optional[S3Secrets] = None
    elasticache: Optional[ElastiCacheSecrets] = None
    bedrock: Optional[BedrockSecrets] = None

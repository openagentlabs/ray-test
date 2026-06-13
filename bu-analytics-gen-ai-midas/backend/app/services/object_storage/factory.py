"""Construct ``ObjectStorageBackend`` from settings and ``ApplicationSecretsBundle``.

Resolution order for the upload backend:
  1. ``bundle.s3`` loaded from AWS Secrets Manager (``AWS_S3_SECRET_ID``).
  2. Direct env config ``S3_BUCKET_NAME`` / ``S3_REGION`` (uses default boto3
     credentials chain: IRSA, EC2 instance profile, or ambient ``AWS_*`` vars).
  3. Local filesystem under ``UPLOAD_DIR`` (safe fallback).

Any failure while building or probing the S3 client is caught and the app
falls back to local storage so the service always starts.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Optional

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from app.core.boto_session import build_boto3_session
from app.services.object_storage.contracts import ObjectStorageBackend
from app.services.object_storage.local_object_storage import LocalObjectStorage
from app.services.object_storage.s3_object_storage import S3ObjectStorage

if TYPE_CHECKING:
    from app.core.config import Settings
    from app.core.secrets.models import ApplicationSecretsBundle, S3Secrets

logger = logging.getLogger(__name__)


def _s3_client(settings: "Settings", s3_sec: "S3Secrets"):
    region = s3_sec.region or settings.AWS_REGION or settings.AWS_DEFAULT_REGION
    if s3_sec.access_key_id and s3_sec.secret_access_key:
        kw: dict = {
            "aws_access_key_id": s3_sec.access_key_id,
            "aws_secret_access_key": s3_sec.secret_access_key,
        }
        if s3_sec.session_token:
            kw["aws_session_token"] = s3_sec.session_token
        if region:
            kw["region_name"] = region
        return boto3.client("s3", **kw)
    return build_boto3_session(settings.AWS_PROFILE).client("s3", region_name=region)


def _s3_from_env(settings: "Settings") -> Optional["S3Secrets"]:
    """Build a keyless ``S3Secrets`` from ``S3_BUCKET_NAME`` / ``S3_REGION`` env vars."""
    bucket = (getattr(settings, "S3_BUCKET_NAME", None) or "").strip()
    if not bucket:
        return None
    from app.core.secrets.models import S3Secrets

    region = (
        (getattr(settings, "S3_REGION", None) or "").strip()
        or (settings.AWS_REGION or "").strip()
        or (settings.AWS_DEFAULT_REGION or "").strip()
        or None
    )
    return S3Secrets(
        access_key_id=None,
        secret_access_key=None,
        session_token=None,
        region=region,
        bucket=bucket,
    )


def _try_build_s3_backend(
    settings: "Settings", s3_sec: "S3Secrets", prefix: str
) -> Optional[S3ObjectStorage]:
    """Build S3 client and probe the bucket; return ``None`` on any failure."""
    if not s3_sec.bucket:
        return None
    try:
        client = _s3_client(settings, s3_sec)
        # Connectivity probe: head_bucket validates credentials + bucket access
        # before we commit to the S3 backend at startup.
        client.head_bucket(Bucket=s3_sec.bucket)
        return S3ObjectStorage(client, s3_sec.bucket, key_prefix=prefix)
    except (ClientError, BotoCoreError, Exception) as exc:
        logger.warning(
            "S3 backend unavailable (bucket=%s region=%s): %s - falling back to local storage",
            s3_sec.bucket,
            s3_sec.region,
            exc,
        )
        return None


def build_upload_object_storage(
    settings: "Settings",
    bundle: "ApplicationSecretsBundle",
) -> ObjectStorageBackend:
    """
    Returns S3 when configured via secret or env; local ``UPLOAD_DIR`` otherwise.

    Order: ``bundle.s3`` → env ``S3_BUCKET_NAME`` → ``LocalObjectStorage``.
    Prefix comes from ``S3_UPLOAD_KEY_PREFIX`` (default ``uploads``).
    """
    prefix = getattr(settings, "S3_UPLOAD_KEY_PREFIX", None) or "uploads"

    candidate: Optional["S3Secrets"] = bundle.s3
    if candidate is not None and candidate.bucket:
        backend = _try_build_s3_backend(settings, candidate, prefix)
        if backend is not None:
            logger.info("Using S3 object storage (bucket=%s, source=secret)", candidate.bucket)
            return backend

    env_candidate = _s3_from_env(settings)
    if env_candidate is not None:
        backend = _try_build_s3_backend(settings, env_candidate, prefix)
        if backend is not None:
            logger.info(
                "Using S3 object storage (bucket=%s, source=env)", env_candidate.bucket
            )
            return backend

    logger.info("Using local object storage at %s", settings.UPLOAD_DIR)
    return LocalObjectStorage(Path(settings.UPLOAD_DIR))

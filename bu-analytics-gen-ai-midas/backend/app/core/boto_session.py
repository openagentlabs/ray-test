"""
Single place to construct ``boto3.Session`` for optional profile vs default credentials.

When ``profile_name`` is unset or blank, ``boto3.Session()`` uses the **default
credential provider chain** (environment variables, shared config, EC2 instance
profile / IMDS, ECS task role, etc.).

When ``profile_name`` is set (e.g. from ``AWS_PROFILE`` in ``.env``), that named
profile is used (SSO, assumed roles, etc.).
"""

from __future__ import annotations

from typing import Any, Optional


def build_boto3_session(profile_name: Optional[str] = None) -> Any:
    """
    Build a boto3 Session.

    :param profile_name: If non-empty, pass to ``boto3.Session(profile_name=...)``.
        If empty/None, use ``boto3.Session()`` so the default chain applies.
    """
    import boto3  # type: ignore

    pn = (profile_name or "").strip() or None
    if pn:
        return boto3.Session(profile_name=pn)
    return boto3.Session()

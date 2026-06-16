"""Bootstrap fields for the first admin user when the logins table is empty."""

from __future__ import annotations

import os
from dataclasses import dataclass

from iam_service.core.errors import AppError, ErrorCodes
from iam_service.core.results import Failure, Result, Success


@dataclass(frozen=True, slots=True)
class DeploymentAdminBootstrapFields:
    """Credentials for ``check_if_new_deployment_can_create_admin``."""

    first_name: str
    last_name: str
    email: str
    password: str


def auto_bootstrap_admin_on_empty_enabled() -> bool:
    """When false, skip automatic admin creation on empty logins table."""
    return os.environ.get("IAM_AUTO_BOOTSTRAP_ADMIN_ON_EMPTY", "true").strip().lower() != "false"


def deployment_admin_bootstrap_fields() -> Result[DeploymentAdminBootstrapFields, AppError]:
    """Resolve bootstrap identity from ``IAM_BOOTSTRAP_*`` environment variables only."""
    first = os.environ.get("IAM_BOOTSTRAP_FIRST_NAME", "").strip()
    last = os.environ.get("IAM_BOOTSTRAP_LAST_NAME", "").strip()
    email = os.environ.get("IAM_BOOTSTRAP_EMAIL", "").strip()
    password = os.environ.get("IAM_BOOTSTRAP_PASSWORD", "").strip()
    missing = [
        key
        for key, val in (
            ("IAM_BOOTSTRAP_FIRST_NAME", first),
            ("IAM_BOOTSTRAP_LAST_NAME", last),
            ("IAM_BOOTSTRAP_EMAIL", email),
            ("IAM_BOOTSTRAP_PASSWORD", password),
        )
        if not val
    ]
    if missing:
        return Failure(
            AppError(
                code=ErrorCodes.VALIDATION,
                message="IAM bootstrap credentials are not configured.",
                detail=("Set in iam.svc/server/.env.local (or process env): " + ", ".join(missing)),
            ),
        )
    if "@" not in email or "." not in email.rsplit("@", maxsplit=1)[-1]:
        return Failure(
            AppError(
                code=ErrorCodes.VALIDATION,
                message="IAM_BOOTSTRAP_EMAIL must be a valid email address.",
                detail=None,
            ),
        )
    return Success(
        DeploymentAdminBootstrapFields(
            first_name=first,
            last_name=last,
            email=email,
            password=password,
        ),
    )

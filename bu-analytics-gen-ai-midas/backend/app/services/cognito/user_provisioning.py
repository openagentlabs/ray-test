"""
Just-in-time (JIT) provisioning of ``UserInDB`` rows for Cognito-authenticated users.

On first successful token exchange we upsert a local user keyed by
``username = f"cg:{sub}"``. The password hash is a throwaway (unusable) random
value so every existing DB-backed flow that expects a ``hashed_password`` column
keeps working, yet no one can authenticate as these users via the legacy
password path.

This keeps downstream code (routes, services, dependencies that consume
``UserInDB.id`` / ``.username`` / ``.email`` / ``.is_active``) completely
unchanged.
"""

from __future__ import annotations

import logging
import secrets as _secrets
from typing import Optional

from app.models.schemas import UserCreate, UserInDB, UserUpdate
from app.models.user_database import user_db

logger = logging.getLogger(__name__)

COGNITO_USERNAME_PREFIX = "cg:"
_MAX_USERNAME_LENGTH = 50  # mirrors UserCreate.username constraint


def _cognito_username(sub: str) -> str:
    """
    Derive a local ``username`` from a Cognito ``sub`` claim.

    Truncates to the schema's 50-char limit. ``sub`` is a UUID (36 chars) so the
    prefix fits with room to spare in practice.
    """
    candidate = f"{COGNITO_USERNAME_PREFIX}{sub}"
    return candidate[:_MAX_USERNAME_LENGTH]


def _default_full_name(claims_name: Optional[str], email: Optional[str], sub: str) -> str:
    if claims_name and claims_name.strip():
        return claims_name.strip()[:100]
    if email:
        return email.strip()[:100]
    return sub[:100]


def get_or_create_from_cognito(
    sub: str,
    email: Optional[str],
    full_name: Optional[str],
) -> UserInDB:
    """
    Fetch or create the local mirror of a Cognito user.

    Concurrency: ``UserDB.create_user`` is guarded by a uniqueness check on
    ``username`` and a unique index on the ``users`` table. In the unlikely
    case two parallel exchanges race on first login, one insert wins and the
    other reads the winning row here.
    """
    if not sub:
        raise ValueError("Cognito claim 'sub' is required for JIT provisioning")

    username = _cognito_username(sub)
    existing = user_db.get_user_by_username(username)
    if existing is not None:
        # Keep local profile in sync with latest IdP claims (best-effort; failure is non-fatal).
        update_payload = {}
        if email and email != existing.email:
            update_payload["email"] = email
        if full_name and full_name != existing.full_name:
            update_payload["full_name"] = full_name
        if update_payload:
            try:
                updated = user_db.update_user(existing.id, UserUpdate(**update_payload))
                if updated is not None:
                    return _to_user_in_db(updated, existing.hashed_password)
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("Failed to update Cognito mirror for %s: %s", username, exc)
        return existing

    resolved_full_name = _default_full_name(full_name, email, sub)
    create_payload = UserCreate(
        username=username,
        full_name=resolved_full_name,
        email=email,
        # Unusable random password: Cognito users never authenticate via the legacy path.
        # Still bcrypt-hashed downstream by user_db.create_user.
        password=_secrets.token_urlsafe(48),
        is_active=True,
    )
    created = user_db.create_user(create_payload)
    if created is not None:
        logger.info("Provisioned Cognito user mirror: %s", username)
        return created

    # Race: another coroutine inserted first. Read back the winning row.
    refetched = user_db.get_user_by_username(username)
    if refetched is None:
        raise RuntimeError(f"Failed to provision user for sub={sub!r}")
    return refetched


def _to_user_in_db(user, hashed_password: str) -> UserInDB:
    """Adapt ``User`` (no hashed_password) + hash back to ``UserInDB`` for dependency compatibility."""
    return UserInDB(
        id=user.id,
        username=user.username,
        full_name=user.full_name,
        email=user.email,
        hashed_password=hashed_password,
        is_active=user.is_active,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )

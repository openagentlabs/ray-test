"""
Facade for server-side session lifecycle (SRP: callers depend on SessionManager, not raw stores).
"""

from __future__ import annotations

import uuid
from typing import Optional, Tuple

from app.core.logging_config import get_logger
from app.core.session.contracts import ISessionAuthenticator, ISessionStore
from app.models.schemas import UserInDB
from app.models.user_database import user_db
from app.services.auth_service import verify_token

logger = get_logger(__name__)


class SessionManager(ISessionAuthenticator):
    """Coordinates JWT claims (`sid`) with the configured ISessionStore (implements ISessionAuthenticator)."""

    def __init__(self, store: ISessionStore, ttl_seconds: int) -> None:
        self._store = store
        self._ttl_seconds = max(600, int(ttl_seconds))

    @property
    def ttl_seconds(self) -> int:
        return self._ttl_seconds

    async def create_session(self, username: str) -> str:
        session_id = str(uuid.uuid4())
        await self._store.save(session_id, username, self._ttl_seconds)
        return session_id

    async def invalidate_access_token(self, token: str) -> None:
        data = verify_token(token)
        if data and data.session_id:
            await self._store.delete(data.session_id)

    async def _authenticate_verbose(self, token: str) -> Tuple[Optional[UserInDB], str]:
        """
        Internal implementation shared by authenticate_access_token and
        authenticate_access_token_verbose. Returns ``(user, reason)`` where
        ``reason`` is one of: ``"ok"`` | ``"jwt_invalid"`` | ``"user_not_found"``
        | ``"sid_invalid"``.
        """
        data = verify_token(token)
        if data is None or not data.username:
            return None, "jwt_invalid"
        user = user_db.get_user_by_username(data.username)
        if user is None or not user.is_active:
            return None, "user_not_found"
        if data.session_id:
            ok = await self._store.is_valid(data.session_id, data.username)
            if not ok:
                return None, "sid_invalid"
            # Slide the window: every successful API call resets the idle clock.
            # Best-effort: a failure to extend must never block a validated request.
            try:
                await self._store.extend(data.session_id, self._ttl_seconds)
            except Exception:
                logger.warning(
                    "session_extend_failed — sid TTL not refreshed; session will expire at original window",
                    extra={"event": "session_extend_failed"},
                )
        return user, "ok"

    async def authenticate_access_token(self, token: str) -> Optional[UserInDB]:
        """
        Validate JWT, user state, and optional server-side session (``sid`` claim).
        Tokens without ``sid`` remain valid (backward compatibility); tokens with ``sid``
        must match the store.
        """
        user, reason = await self._authenticate_verbose(token)
        if user is None:
            logger.info(
                "session_auth_rejected",
                extra={
                    "event": "session_auth_classify",
                    "reason": reason,
                },
            )
        return user

    async def authenticate_access_token_verbose(
        self, token: str
    ) -> Tuple[Optional[UserInDB], str]:
        """
        Same as ``authenticate_access_token`` but also returns the rejection reason
        string so callers can emit precise diagnostic logs without re-decoding the token.

        Args:
            token: Raw JWT Bearer string.

        Returns:
            ``(UserInDB, "ok")`` on success; ``(None, reason)`` on failure where
            ``reason`` is one of ``"jwt_invalid"``, ``"user_not_found"``,
            ``"sid_invalid"``.
        """
        return await self._authenticate_verbose(token)

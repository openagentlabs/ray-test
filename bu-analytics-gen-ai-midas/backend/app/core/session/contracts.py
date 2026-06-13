"""
Abstract contracts for session storage and Redis URL resolution (OCP: extend via new subclasses).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional, Protocol, Tuple, runtime_checkable

from app.models.schemas import UserInDB


class IRedisUrlProvider(ABC):
    """Strategy: produce a Redis connection URL or defer to the next provider."""

    @abstractmethod
    def get_redis_url(self) -> Optional[str]:
        """Return a non-empty redis/rediss URL, or None if this provider does not apply."""


class ISessionStore(ABC):
    """Persistence for server-side access sessions (keyed by opaque session id)."""

    @abstractmethod
    async def save(self, session_id: str, username: str, ttl_seconds: int) -> None:
        """Create or replace a session record."""

    @abstractmethod
    async def is_valid(self, session_id: str, username: str) -> bool:
        """True if session exists, TTL not expired, and bound username matches."""

    @abstractmethod
    async def delete(self, session_id: str) -> None:
        """Invalidate a single session."""

    @abstractmethod
    async def extend(self, session_id: str, ttl_seconds: int) -> None:
        """Slide the TTL of an existing session forward. No-op if the key is absent."""


@runtime_checkable
class ISessionAuthenticator(Protocol):
    """
    Facade used by auth routes and session middleware (DIP: depend on protocol, not SessionManager).
    Implemented by SessionManager.
    """

    @property
    def ttl_seconds(self) -> int: ...

    async def create_session(self, username: str) -> str: ...

    async def invalidate_access_token(self, token: str) -> None: ...

    async def authenticate_access_token(self, token: str) -> Optional[UserInDB]: ...

    async def authenticate_access_token_verbose(
        self, token: str
    ) -> Tuple[Optional[UserInDB], str]:
        """
        Same as authenticate_access_token but returns ``(user, rejection_reason)`` so
        callers (e.g. SessionValidationMiddleware) can emit structured diagnostics.
        ``rejection_reason`` is one of:
          - ``"ok"``             — authenticated successfully
          - ``"jwt_invalid"``    — JWT could not be decoded / expired / bad signature
          - ``"user_not_found"`` — username not in DB or account inactive
          - ``"sid_invalid"``    — JWT valid but server-side session missing / expired
        """
        ...

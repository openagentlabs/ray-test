"""
Which URL paths skip optional Bearer validation in session middleware (Open/Closed: add rules via new policy subclasses).
"""

from __future__ import annotations

from abc import ABC, abstractmethod


def normalize_path(path: str) -> str:
    if not path or path == "/":
        return "/"
    return "/" + path.strip("/")


class IPublicPathPolicy(ABC):
    """Strategy: decide if a path may proceed without token validation."""

    @abstractmethod
    def allows_anonymous_bearer_skip(self, path: str) -> bool:
        """True → middleware does not require a valid token (routes may still use Depends)."""


class DefaultSessionSkipPathPolicy(IPublicPathPolicy):
    """
    Default rules: health/docs + unauthenticated auth endpoints.
    """

    def __init__(
        self,
        exact_public: frozenset[str] | None = None,
        auth_unauthenticated: frozenset[str] | None = None,
    ) -> None:
        self._exact_public = exact_public or _DEFAULT_EXACT_PUBLIC
        self._auth_unauthenticated = auth_unauthenticated or _DEFAULT_AUTH_UNAUTHENTICATED

    def allows_anonymous_bearer_skip(self, path: str) -> bool:
        p = normalize_path(path)
        return p in self._exact_public or p in self._auth_unauthenticated


_DEFAULT_EXACT_PUBLIC: frozenset[str] = frozenset(
    {
        "/",
        "/health",
        "/docs",
        "/redoc",
        "/openapi.json",
        "/favicon.ico",
    }
)

_DEFAULT_AUTH_UNAUTHENTICATED: frozenset[str] = frozenset(
    {
        "/api/v1/auth/login",
        "/api/v1/auth/register",
        "/api/v1/auth/refresh",
    }
)

default_session_skip_path_policy = DefaultSessionSkipPathPolicy()

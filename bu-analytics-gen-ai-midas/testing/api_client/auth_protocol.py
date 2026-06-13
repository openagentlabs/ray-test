"""Authentication header providers for :class:`MidasHttpClient`."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from testing.api_client.credentials import MidasSessionCredentials


@runtime_checkable
class AuthHeaderProvider(Protocol):
    """Supplies per-request auth headers (Bearer + optional session + cookies)."""

    def request_headers(self) -> dict[str, str]:
        """Return headers to merge for each API call."""
        ...


class StaticBearerAuthProvider:
    """Wraps :class:`MidasSessionCredentials` for static token / post-Playwright injection."""

    def __init__(self, credentials: MidasSessionCredentials) -> None:
        self._credentials = credentials

    def request_headers(self) -> dict[str, str]:
        return self._credentials.request_headers()
